from rest_framework.routers import DefaultRouter

from omacrm.core.api.viewsets import RecordViewSet
from omacrm.core.metadata.registry import registry


def build_api_router() -> DefaultRouter:
    """Create one REST endpoint per registered entity type."""

    router = DefaultRouter()
    for entity_type, entity in registry.entities().items():
        viewset = type(
            f"{entity_type}ViewSet",
            (RecordViewSet,),
            {
                "entity_type": entity_type,
                "search_fields": list(entity.search_fields),
                "ordering_fields": "__all__",
                "ordering": list(entity.ordering),
            },
        )
        router.register(entity_type.lower(), viewset, basename=entity_type.lower())
    return router


router = build_api_router()
