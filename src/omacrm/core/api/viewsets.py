from rest_framework import viewsets
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import BasePermission, IsAuthenticated

from omacrm.core.api.filters import parse_where
from omacrm.core.api.serializers import serializer_for
from omacrm.core.metadata.registry import registry
from omacrm.core.services.acl import AclService

METHOD_ACTION_MAP = {
    "GET": "read",
    "HEAD": "read",
    "OPTIONS": "read",
    "POST": "create",
    "PUT": "edit",
    "PATCH": "edit",
    "DELETE": "delete",
}


class AclPermission(BasePermission):
    def has_permission(self, request, view):
        entity_type = getattr(view, "entity_type", "")
        if not entity_type:
            return True
        action = METHOD_ACTION_MAP.get(request.method, "read")
        return AclService.check(request.user, entity_type, action)

    def has_object_permission(self, request, view, obj):
        entity_type = getattr(view, "entity_type", "")
        if not entity_type:
            return True
        action = METHOD_ACTION_MAP.get(request.method, "read")
        return AclService.check(request.user, entity_type, action, obj)


class RecordViewSet(viewsets.ModelViewSet):
    """Generic, metadata-driven and ACL-scoped record API."""

    permission_classes = [IsAuthenticated, AclPermission]
    entity_type = ""

    def get_queryset(self):
        queryset = registry.model_for(self.entity_type).objects.all()
        if registry.is_dynamic(self.entity_type):
            queryset = queryset.filter(entity_type=self.entity_type)
        return AclService.scope_queryset(
            self.request.user, self.entity_type, queryset, "read"
        )

    def get_serializer_class(self):
        return serializer_for(self.entity_type)

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        where = self.request.query_params.get("where")
        if where:
            queryset = queryset.filter(parse_where(self.entity_type, where))
        return queryset

    def perform_create(self, serializer):
        if not AclService.check(self.request.user, self.entity_type, "create"):
            raise PermissionDenied()
        extra = {}
        model_field_names = {
            field.name for field in serializer.Meta.model._meta.concrete_fields
        }
        if "created_by" in model_field_names:
            extra["created_by"] = self.request.user
        if "modified_by" in model_field_names:
            extra["modified_by"] = self.request.user
        if registry.is_dynamic(self.entity_type):
            extra["entity_type"] = self.entity_type
        serializer.save(**extra)
        self._apply_links(serializer.instance)

    def perform_update(self, serializer):
        extra = {}
        model_field_names = {
            field.name for field in serializer.Meta.model._meta.concrete_fields
        }
        if "modified_by" in model_field_names:
            extra["modified_by"] = self.request.user
        serializer.save(**extra)
        self._apply_links(serializer.instance)

    def _apply_links(self, instance):
        definitions = registry.link_definitions(self.entity_type)
        if not definitions:
            return
        from omacrm.core.services import relations

        for name, definition in definitions.items():
            if name not in self.request.data:
                continue
            value = self.request.data.get(name) or []
            if isinstance(value, str):
                value = [value]
            elif not isinstance(value, (list, tuple)):
                value = [value]
            ids = [int(item) for item in value if str(item).isdigit()]
            model = registry.model_for(definition.target_entity)
            targets = list(model.objects.filter(pk__in=ids))
            relations.set_related(instance, name, targets)

    def perform_destroy(self, instance):
        if not AclService.check(
            self.request.user, self.entity_type, "delete", instance
        ):
            raise PermissionDenied()
        instance.delete()


class DynamicRecordViewSet(RecordViewSet):
    """Resolve a runtime custom entity from the URL (no restart needed)."""

    @property
    def entity_type(self):
        return self.kwargs.get("entity_type", "")

    def initial(self, request, *args, **kwargs):
        if not registry.is_dynamic(self.entity_type):
            raise NotFound("Unknown entity type.")
        super().initial(request, *args, **kwargs)
