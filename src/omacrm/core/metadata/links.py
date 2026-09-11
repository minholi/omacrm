"""Resolve ``CustomLink`` rows into per-entity link definitions.

Links are described from one side (``entity_type`` → ``link_entity``); the
reverse link is derived automatically so both entities expose the relationship.
"""

from dataclasses import dataclass

from django.db import OperationalError, ProgrammingError

REVERSE_TYPES = {
    "belongsTo": "hasMany",
    "hasMany": "belongsTo",
    "manyToMany": "manyToMany",
}


@dataclass
class LinkDefinition:
    entity_type: str
    name: str
    label: str
    link_type: str
    target_entity: str
    foreign_name: str
    forward: bool
    custom_link_pk: int

    @property
    def multiple(self) -> bool:
        return self.link_type != "belongsTo"

    @property
    def field_type(self) -> str:
        return "linkMultiple" if self.multiple else "link"


def _reverse_label(row) -> str:
    from omacrm.core.metadata.registry import registry

    try:
        source = registry.get(row.entity_type)
        target = registry.get(row.link_entity)
    except KeyError:
        return row.reverse_label

    if row.link_type == "belongsTo":
        # The target has many sources: Account.projects -> "Projects".
        return source.display_label_plural
    if row.link_type == "hasMany":
        # The target belongs to the source: Project.account -> "Account".
        return source.display_label
    return target.display_label_plural


def link_definitions(entity_type: str) -> dict[str, LinkDefinition]:
    from omacrm.core.models import CustomLink

    definitions: dict[str, LinkDefinition] = {}
    try:
        rows = list(CustomLink.objects.filter(is_active=True))
    except (OperationalError, ProgrammingError):
        return definitions

    for row in rows:
        if row.entity_type == entity_type:
            definitions[row.name] = LinkDefinition(
                entity_type=entity_type,
                name=row.name,
                label=row.forward_label,
                link_type=row.link_type,
                target_entity=row.link_entity,
                foreign_name=row.foreign_name,
                forward=True,
                custom_link_pk=row.pk,
            )
        if row.link_entity == entity_type and row.foreign_name:
            definitions[row.foreign_name] = LinkDefinition(
                entity_type=entity_type,
                name=row.foreign_name,
                label=_reverse_label(row),
                link_type=REVERSE_TYPES.get(row.link_type, "hasMany"),
                target_entity=row.entity_type,
                foreign_name=row.name,
                forward=False,
                custom_link_pk=row.pk,
            )
    return definitions
