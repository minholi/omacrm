"""Kanban boards driven by an entity status field."""

MAX_PER_COLUMN = 100


def kanban_config(entity_type: str):
    """Return the Kanban configuration of an entity, or ``None``."""

    from omacrm.core.metadata.registry import registry

    if not registry.has(entity_type):
        return None
    entity = registry.get(entity_type)
    field_name = entity.kanban_field
    if not field_name:
        return None
    field_def = registry.fields(entity_type).get(field_name)
    if field_def is None:
        return None
    choices = _choices(entity_type, field_def)
    if not choices:
        return None
    return {
        "entity_type": entity_type,
        "field": field_name,
        "field_def": field_def,
        "label": field_def.display_label,
        "choices": choices,
    }


def _choices(entity_type: str, field_def) -> list[tuple[str, str]]:
    if field_def.options:
        return [(str(value), str(label)) for value, label in field_def.options]
    model_field = getattr(field_def, "model_field", None)
    if not model_field:
        return []
    from omacrm.core.metadata.registry import registry

    try:
        model = registry.model_for(entity_type)
        choices = model._meta.get_field(model_field).choices or []
    except Exception:  # noqa: BLE001 - metadata may be incomplete
        return []
    return [(str(value), str(label)) for value, label in choices]


def current_status(record, field_def) -> str:
    if field_def.custom:
        value = (record.custom_data or {}).get(field_def.name)
    else:
        value = getattr(record, field_def.name, None)
    return "" if value is None else str(value)


def board(entity_type: str, user, max_per_column: int = MAX_PER_COLUMN):
    """Records grouped by status column, ACL-scoped and in the user's order.

    Cards the user arranged come first within their column, in the stored
    order; the rest follow by the entity's metadata ordering. With no stored
    rows the result is exactly the historical metadata-ordered board.
    """

    from omacrm.core.metadata.registry import registry
    from omacrm.core.models import KanbanOrder
    from omacrm.core.services.acl import AclService

    config = kanban_config(entity_type)
    if config is None:
        return None

    model = registry.model_for(entity_type)
    queryset = model.objects.all()
    if registry.is_dynamic(entity_type):
        queryset = queryset.filter(entity_type=entity_type)
    queryset = AclService.scope_queryset(user, entity_type, queryset, "read")
    ordering = registry.get(entity_type).ordering or ["-created_at"]
    queryset = queryset.order_by(*ordering)

    stored = {
        row.entity_id: (row.group, row.order)
        for row in KanbanOrder.objects.filter(user=user, entity_type=entity_type)
    }

    window = max_per_column * 10
    if stored:
        ordered_records = list(queryset.filter(pk__in=stored)[:window])
        ordered_records.sort(key=lambda record: stored[record.pk])
        other_records = list(queryset.exclude(pk__in=stored)[:window])
    else:
        ordered_records = []
        other_records = list(queryset[:window])

    buckets: dict[str, list] = {value: [] for value, _label in config["choices"]}
    other: list = []

    def place(index, record):
        value = current_status(record, config["field_def"])
        target = buckets.get(value)
        if target is None:
            target = other
        if len(target) < max_per_column:
            target.append((index, record))

    for index, record in enumerate(ordered_records):
        place(index, record)
    for index, record in enumerate(other_records, start=len(ordered_records)):
        place(index, record)

    def sort_key(item, group_value):
        index, record = item
        entry = stored.get(record.pk)
        if entry is not None and entry[0] == group_value:
            return (0, entry[1], index)
        return (1, index, 0)

    for value, items in buckets.items():
        items.sort(key=lambda item: sort_key(item, value))
    other.sort(key=lambda item: sort_key(item, ""))

    columns = [
        {
            "value": value,
            "label": label,
            "records": [record for _index, record in buckets[value]],
        }
        for value, label in config["choices"]
    ]
    if other:
        columns.append(
            {
                "value": "",
                "label": "No value",
                "records": [record for _index, record in other],
            }
        )
    return {"config": config, "columns": columns}


def reorder(user, entity_type: str, group: str, ids) -> None:
    """Persist the new order of one Kanban column for one user.

    ``ids`` is the list of record primary keys in their new order; every id
    must be visible to the user and currently sit in ``group``. The write is
    batched, so a full column costs one insert statement, not one per card.
    """

    from omacrm.core.metadata.registry import registry
    from omacrm.core.models import KanbanOrder
    from omacrm.core.services.acl import AclService

    config = kanban_config(entity_type)
    if config is None:
        raise ValueError("Kanban is not enabled for this entity.")

    valid = {choice_value for choice_value, _label in config["choices"]}
    if group not in valid and group != "":
        raise ValueError("Unknown Kanban column.")

    ordered_ids: list[int] = []
    seen: set[int] = set()
    for raw in ids or []:
        try:
            pk = int(raw)
        except (TypeError, ValueError):
            raise ValueError("Invalid record id.")
        if pk not in seen:
            seen.add(pk)
            ordered_ids.append(pk)
    if not ordered_ids:
        return

    model = registry.model_for(entity_type)
    queryset = model.objects.all()
    if registry.is_dynamic(entity_type):
        queryset = queryset.filter(entity_type=entity_type)
    queryset = AclService.scope_queryset(user, entity_type, queryset, "read")
    records = {record.pk: record for record in queryset.filter(pk__in=ordered_ids)}
    if len(records) != len(ordered_ids):
        raise ValueError("Unknown or inaccessible record.")

    field_def = config["field_def"]
    for pk in ordered_ids:
        if current_status(records[pk], field_def) != group:
            raise ValueError("Record is not in this column.")

    rows = [
        KanbanOrder(
            user=user,
            entity_type=entity_type,
            entity_id=pk,
            group=group,
            order=index,
        )
        for index, pk in enumerate(ordered_ids)
    ]
    KanbanOrder.objects.bulk_create(
        rows,
        update_conflicts=True,
        update_fields=["group", "order"],
        unique_fields=["user", "entity_type", "entity_id"],
    )


def move_record(record, entity_type: str, field_name: str, value: str) -> None:
    """Update the status field of a record and drop its saved position.

    A card moved to another column has no stored order in that column, so it
    lands at the end; keeping the old row would leave a stale position behind.
    """

    from omacrm.core.models import KanbanOrder

    config = kanban_config(entity_type)
    if config is None or config["field"] != field_name:
        raise ValueError("Unknown Kanban field.")
    valid = {choice_value for choice_value, _label in config["choices"]}
    if value not in valid:
        raise ValueError("Unknown status value.")

    field_def = config["field_def"]
    previous = current_status(record, field_def)
    if field_def.custom:
        data = dict(record.custom_data or {})
        data[field_name] = value
        record.custom_data = data
        record.save(update_fields=["custom_data"])
    else:
        setattr(record, field_name, value)
        record.save(update_fields=[field_name])

    if previous != value:
        KanbanOrder.objects.filter(
            entity_type=entity_type, entity_id=record.pk
        ).delete()
