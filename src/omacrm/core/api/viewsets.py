from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission, IsAuthenticated

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

    def perform_update(self, serializer):
        extra = {}
        model_field_names = {
            field.name for field in serializer.Meta.model._meta.concrete_fields
        }
        if "modified_by" in model_field_names:
            extra["modified_by"] = self.request.user
        serializer.save(**extra)

    def perform_destroy(self, instance):
        if not AclService.check(
            self.request.user, self.entity_type, "delete", instance
        ):
            raise PermissionDenied()
        instance.delete()
