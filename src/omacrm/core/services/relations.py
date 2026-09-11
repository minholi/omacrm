"""Read and write ``CustomLink`` relationships stored in ``RecordLink``.

Each relation is stored twice: once under the forward link name and once under
the reverse name on the target record, so both sides can be listed uniformly.
"""

from django.db import OperationalError, ProgrammingError


def _entity_type(record) -> str:
    from omacrm.core.metadata.registry import registry

    entity_type = registry.entity_type_for_instance(record)
    if not entity_type and hasattr(record, "entity_type"):
        entity_type = record.entity_type
    return entity_type or ""


def _definition(entity_type: str, link_name: str):
    from omacrm.core.metadata.links import link_definitions

    return link_definitions(entity_type).get(link_name)


def _reverse_definition(definition):
    if not definition or not definition.foreign_name:
        return None
    return _definition(definition.target_entity, definition.foreign_name)


def linked_ids(entity_type: str, pk, link_name: str) -> list[int]:
    from omacrm.core.models import RecordLink

    try:
        return list(
            RecordLink.objects.filter(
                source_type=entity_type, source_id=pk, link=link_name
            ).values_list("target_id", flat=True)
        )
    except (OperationalError, ProgrammingError):
        return []


def get_related(record, link_name: str) -> list:
    from omacrm.core.metadata.registry import registry
    from omacrm.core.models import RecordLink

    entity_type = _entity_type(record)
    definition = _definition(entity_type, link_name)
    if definition is None:
        return []

    rows = list(
        RecordLink.objects.filter(
            source_type=entity_type, source_id=record.pk, link=link_name
        )
    )
    if not rows:
        return []
    model = registry.model_for(definition.target_entity)
    records = {obj.pk: obj for obj in model.objects.filter(pk__in=[r.target_id for r in rows])}
    return [records[row.target_id] for row in rows if row.target_id in records]


def related_map(records, link_name: str) -> dict[int, list]:
    """Batch version of :func:`get_related` for changelist columns."""

    from omacrm.core.metadata.registry import registry
    from omacrm.core.models import RecordLink

    records = list(records)
    if not records:
        return {}
    entity_type = _entity_type(records[0])
    definition = _definition(entity_type, link_name)
    if definition is None:
        return {}

    rows = RecordLink.objects.filter(
        source_type=entity_type,
        source_id__in=[record.pk for record in records],
        link=link_name,
    )
    target_ids = {row.target_id for row in rows}
    model = registry.model_for(definition.target_entity)
    targets = {obj.pk: obj for obj in model.objects.filter(pk__in=target_ids)}

    result: dict[int, list] = {record.pk: [] for record in records}
    for row in rows:
        target = targets.get(row.target_id)
        if target is not None:
            result.setdefault(row.source_id, []).append(target)
    return result


def add_related(record, link_name: str, target) -> None:
    from omacrm.core.models import RecordLink

    entity_type = _entity_type(record)
    definition = _definition(entity_type, link_name)
    if definition is None:
        raise ValueError(f"Unknown link: {entity_type}.{link_name}")

    if not definition.multiple:
        clear_related(record, link_name)

    RecordLink.objects.get_or_create(
        source_type=entity_type,
        source_id=record.pk,
        link=link_name,
        target_type=definition.target_entity,
        target_id=target.pk,
    )
    reverse = _reverse_definition(definition)
    if reverse is not None:
        RecordLink.objects.get_or_create(
            source_type=definition.target_entity,
            source_id=target.pk,
            link=reverse.name,
            target_type=entity_type,
            target_id=record.pk,
        )


def remove_related(record, link_name: str, target=None, target_id=None) -> int:
    from django.db.models import Q

    from omacrm.core.models import RecordLink

    entity_type = _entity_type(record)
    definition = _definition(entity_type, link_name)
    if definition is None:
        return 0

    if target_id is None and target is not None:
        target_id = target.pk

    condition = Q(
        source_type=entity_type, source_id=record.pk, link=link_name
    )
    if target_id is not None:
        condition &= Q(target_id=target_id)

    rows = list(RecordLink.objects.filter(condition))
    if not rows:
        return 0
    RecordLink.objects.filter(condition).delete()

    reverse = _reverse_definition(definition)
    if reverse is not None:
        RecordLink.objects.filter(
            source_type=definition.target_entity,
            link=reverse.name,
            target_type=entity_type,
            target_id=record.pk,
            source_id__in=[row.target_id for row in rows],
        ).delete()
    return len(rows)


def clear_related(record, link_name: str) -> int:
    return remove_related(record, link_name)


def set_related(record, link_name: str, targets) -> None:
    """Replace the current targets of ``link_name`` with ``targets``."""

    entity_type = _entity_type(record)
    definition = _definition(entity_type, link_name)
    if definition is None:
        raise ValueError(f"Unknown link: {entity_type}.{link_name}")

    targets = list(targets)
    if not definition.multiple:
        targets = targets[:1]

    current = set(linked_ids(entity_type, record.pk, link_name))
    wanted = {target.pk for target in targets}

    for target in targets:
        if target.pk not in current:
            add_related(record, link_name, target)
    for target_id in current - wanted:
        remove_related(record, link_name, target_id=target_id)


def delete_links_for_entity(entity_type: str, pk=None) -> int:
    """Remove links where the entity (or one record) is either side."""

    from django.db.models import Q

    from omacrm.core.models import RecordLink

    condition = Q(source_type=entity_type) | Q(target_type=entity_type)
    if pk is not None:
        condition &= (
            Q(source_type=entity_type, source_id=pk)
            | Q(target_type=entity_type, target_id=pk)
        )
    return RecordLink.objects.filter(condition).delete()[0]
