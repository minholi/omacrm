from rest_framework import serializers

from omacrm.core.metadata.registry import registry

_SERIALIZER_CACHE: dict[str, type] = {}


def _link_representation(entity_type: str):
    from omacrm.core.services import relations

    def to_representation(self, instance):
        data = serializers.ModelSerializer.to_representation(self, instance)
        for name, definition in registry.link_definitions(entity_type).items():
            records = relations.get_related(instance, name)
            if definition.multiple:
                data[name] = [record.pk for record in records]
            else:
                data[name] = records[0].pk if records else None
        return data

    return to_representation


def serializer_for(entity_type: str) -> type:
    """Build (and cache) a ModelSerializer from the metadata registry."""

    if entity_type in _SERIALIZER_CACHE:
        return _SERIALIZER_CACHE[entity_type]

    model = registry.model_for(entity_type)
    model_field_names = {field.name for field in model._meta.concrete_fields}
    metadata_fields = registry.fields(entity_type)

    field_names = ["id"]
    for name, field_def in metadata_fields.items():
        if field_def.custom:
            continue
        if name in model_field_names:
            field_names.append(name)
    for name in ("created_at", "modified_at", "created_by", "modified_by", "custom_data"):
        if name in model_field_names and name not in field_names:
            field_names.append(name)

    read_only = [
        name
        for name, field_def in metadata_fields.items()
        if field_def.read_only and name in field_names
    ]

    meta = type(
        "Meta",
        (),
        {
            "model": model,
            "fields": field_names,
            "read_only_fields": read_only,
        },
    )
    serializer_class = type(
        f"{entity_type}Serializer",
        (serializers.ModelSerializer,),
        {"Meta": meta, "to_representation": _link_representation(entity_type)},
    )
    _SERIALIZER_CACHE[entity_type] = serializer_class
    return serializer_class


def invalidate_serializer_cache():
    _SERIALIZER_CACHE.clear()
