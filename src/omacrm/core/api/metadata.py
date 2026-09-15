"""Staff-only REST management of the metadata definitions.

Business records are served by the metadata-driven ``/api/v1/{entity}/``
endpoints; this module manages the definitions those endpoints are built from:
custom entities, custom fields, layouts and custom relationships. Writes reuse
the same signals as the admin (registry invalidation, entity materialization
and URLconf refresh), so changes are live immediately.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.routers import DefaultRouter

from omacrm.core.metadata.registry import registry
from omacrm.core.models import CustomEntity, CustomField, CustomLink, Layout


class CleanModelSerializer(serializers.ModelSerializer):
    """Run the model's ``full_clean()`` so admin validation applies to the API."""

    def create(self, validated_data):
        instance = self.Meta.model(**validated_data)
        self._full_clean(instance)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        for name, value in validated_data.items():
            setattr(instance, name, value)
        self._full_clean(instance)
        instance.save()
        return instance

    def _full_clean(self, instance):
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                raise serializers.ValidationError(exc.message_dict) from exc
            raise serializers.ValidationError(exc.messages) from exc

    def validate_entity_type(self, value):
        if value and not registry.has(value):
            raise serializers.ValidationError("Unknown entity type.")
        return value


class CustomEntitySerializer(CleanModelSerializer):
    class Meta:
        model = CustomEntity
        fields = [
            "id",
            "name",
            "label",
            "label_plural",
            "description",
            "template",
            "icon",
            "color",
            "show_in_menu",
            "menu_order",
            "show_in_calendar",
            "status_field",
            "stream",
            "sort_field",
            "sort_direction",
            "search_fields",
            "duplicate_check_fields",
            "is_active",
            "created_at",
            "modified_at",
        ]
        read_only_fields = ["id", "created_at", "modified_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is not None and "template" in attrs:
            if attrs["template"] != self.instance.template:
                raise serializers.ValidationError(
                    {"template": "The template is locked after creation."}
                )
        return attrs


class CustomFieldSerializer(CleanModelSerializer):
    class Meta:
        model = CustomField
        fields = [
            "id",
            "entity_type",
            "name",
            "label",
            "field_type",
            "params",
            "required",
            "read_only",
            "order",
            "is_active",
            "created_at",
            "modified_at",
        ]
        read_only_fields = ["id", "created_at", "modified_at"]


class LayoutSerializer(CleanModelSerializer):
    class Meta:
        model = Layout
        fields = [
            "id",
            "entity_type",
            "layout_name",
            "data",
            "is_custom",
            "created_at",
            "modified_at",
        ]
        read_only_fields = ["id", "created_at", "modified_at"]


class CustomLinkSerializer(CleanModelSerializer):
    class Meta:
        model = CustomLink
        fields = [
            "id",
            "entity_type",
            "name",
            "label",
            "link_type",
            "link_entity",
            "foreign_name",
            "label_foreign",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class MetadataViewSet(viewsets.ModelViewSet):
    """Base viewset for the staff-only metadata resources."""

    permission_classes = [IsAuthenticated, IsAdminUser]


class CustomEntityViewSet(MetadataViewSet):
    queryset = CustomEntity.objects.all()
    serializer_class = CustomEntitySerializer
    search_fields = ["name", "label", "description"]
    ordering = ["name"]


class CustomFieldViewSet(MetadataViewSet):
    queryset = CustomField.objects.all()
    serializer_class = CustomFieldSerializer
    search_fields = ["entity_type", "name", "label"]
    ordering = ["entity_type", "order", "name"]


class LayoutViewSet(MetadataViewSet):
    queryset = Layout.objects.all()
    serializer_class = LayoutSerializer
    search_fields = ["entity_type", "layout_name"]
    ordering = ["entity_type", "layout_name"]


class CustomLinkViewSet(MetadataViewSet):
    queryset = CustomLink.objects.all()
    serializer_class = CustomLinkSerializer
    search_fields = ["entity_type", "name", "link_entity", "foreign_name"]
    ordering = ["entity_type", "name"]


metadata_router = DefaultRouter()
metadata_router.register("entities", CustomEntityViewSet, basename="metadata-entity")
metadata_router.register("fields", CustomFieldViewSet, basename="metadata-field")
metadata_router.register("layouts", LayoutViewSet, basename="metadata-layout")
metadata_router.register("links", CustomLinkViewSet, basename="metadata-link")
