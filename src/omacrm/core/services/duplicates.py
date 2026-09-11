from django.db.models import Q

from omacrm.core.metadata.registry import registry


class DuplicateConflict(Exception):
    """Raised when a record conflicts with existing records."""

    def __init__(self, entity_type: str, duplicates):
        self.entity_type = entity_type
        self.duplicates = list(duplicates)
        super().__init__(
            f"Duplicate {entity_type} found ({len(self.duplicates)} record(s))"
        )


def find_duplicates(entity_type: str, instance):
    """Return records matching the entity's duplicate check fields."""

    entity = registry.get(entity_type)
    model = registry.model_for(entity_type)

    condition = Q()
    has_value = False
    for field_name in entity.duplicate_check_fields:
        value = getattr(instance, field_name, None)
        if value in (None, ""):
            continue
        if isinstance(value, str):
            condition |= Q(**{f"{field_name}__iexact": value})
        else:
            condition |= Q(**{field_name: value})
        has_value = True

    if not has_value:
        return model.objects.none()

    queryset = model.objects.filter(condition)
    if instance.pk:
        queryset = queryset.exclude(pk=instance.pk)
    return queryset


def check_duplicates(entity_type: str, instance) -> None:
    duplicates = find_duplicates(entity_type, instance)
    if duplicates.exists():
        raise DuplicateConflict(entity_type, duplicates)
