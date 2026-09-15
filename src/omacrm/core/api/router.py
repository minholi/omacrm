from rest_framework.routers import DefaultRouter

from omacrm.core.api.viewsets import RecordViewSet
from omacrm.core.metadata.registry import registry


def build_api_router() -> DefaultRouter:
    """Create one REST endpoint per registered built-in entity type.

    Runtime custom entities are served by the capitalized
    ``/api/v1/<Entity>/`` catch-all in the URLconf, so they resolve without a
    restart and never leave stale routes behind after deactivation.
    """

    router = DefaultRouter()
    for entity_type, entity in registry.entities().items():
        if registry.is_dynamic(entity_type):
            continue
        viewset = type(
            f"{entity_type}ViewSet",
            (RecordViewSet,),
            {
                "entity_type": entity_type,
                "ordering_fields": "__all__",
                "ordering": list(entity.ordering),
            },
        )
        router.register(entity_type.lower(), viewset, basename=entity_type.lower())
    return router


router = build_api_router()
