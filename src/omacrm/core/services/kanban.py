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
    """Records grouped by status column, ACL-scoped."""

    from omacrm.core.metadata.registry import registry
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

    buckets: dict[str, list] = {value: [] for value, _label in config["choices"]}
    other: list = []
    for record in queryset[: max_per_column * 10]:
        value = current_status(record, config["field_def"])
        if value in buckets:
            if len(buckets[value]) < max_per_column:
                buckets[value].append(record)
        elif len(other) < max_per_column:
            other.append(record)

    columns = [
        {"value": value, "label": label, "records": buckets[value]}
        for value, label in config["choices"]
    ]
    if other:
        columns.append({"value": "", "label": "No value", "records": other})
    return {"config": config, "columns": columns}


def move_record(record, entity_type: str, field_name: str, value: str) -> None:
    """Update the status field of a record."""

    config = kanban_config(entity_type)
    if config is None or config["field"] != field_name:
        raise ValueError("Unknown Kanban field.")
    valid = {choice_value for choice_value, _label in config["choices"]}
    if value not in valid:
        raise ValueError("Unknown status value.")

    field_def = config["field_def"]
    if field_def.custom:
        data = dict(record.custom_data or {})
        data[field_name] = value
        record.custom_data = data
        record.save(update_fields=["custom_data"])
    else:
        setattr(record, field_name, value)
        record.save(update_fields=[field_name])
