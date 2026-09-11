from django.core.management.base import BaseCommand

from omacrm.core.admin.import_export import invalidate_resource_cache
from omacrm.core.api.serializers import invalidate_serializer_cache
from omacrm.core.metadata.registry import registry


class Command(BaseCommand):
    help = "Rebuild the metadata registry cache and print a summary."

    def handle(self, *args, **options):
        registry.invalidate()
        invalidate_serializer_cache()
        invalidate_resource_cache()
        entities = registry.entities()
        self.stdout.write(
            self.style.SUCCESS(f"Metadata registry loaded: {len(entities)} entity type(s)")
        )
        for entity_type in registry.entity_types():
            fields = registry.fields(entity_type)
            custom = [name for name, field in fields.items() if field.custom]
            custom_note = f", {len(custom)} custom" if custom else ""
            self.stdout.write(f"  - {entity_type}: {len(fields)} fields{custom_note}")
