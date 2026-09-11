from import_export import resources
from import_export.admin import ImportExportMixin
from unfold.contrib.import_export.forms import ExportForm, ImportForm

from omacrm.core.metadata.registry import registry

_RESOURCE_CACHE: dict[str, type] = {}


def resource_for(entity_type: str) -> type:
    """Build (and cache) an import/export Resource from entity metadata."""

    if entity_type in _RESOURCE_CACHE:
        return _RESOURCE_CACHE[entity_type]

    entity = registry.get(entity_type)
    model = registry.model_for(entity_type)
    model_field_names = {field.name for field in model._meta.fields}

    field_names = ["id"] + [
        name
        for name in entity.fields
        if name in model_field_names and name not in {"id"}
    ]

    meta = type(
        "Meta",
        (),
        {
            "model": model,
            "fields": field_names,
            "import_id_fields": ("id",),
        },
    )
    resource_class = type(
        f"{entity_type}Resource", (resources.ModelResource,), {"Meta": meta}
    )
    _RESOURCE_CACHE[entity_type] = resource_class
    return resource_class


def invalidate_resource_cache():
    _RESOURCE_CACHE.clear()


class MetadataImportExportMixin(ImportExportMixin):
    """Metadata-driven CSV/XLSX import and export for entity admins."""

    import_form_class = ImportForm
    export_form_class = ExportForm

    def get_resource_classes(self, request):
        return [resource_for(self.entity_type)]
