from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import display

from omacrm.core.admin.base import MetadataModelAdmin
from omacrm.core.models import CustomEntity


def dynamic_admin_for(entity_type: str):
    """Build a MetadataModelAdmin for a runtime custom entity."""

    admin_entity_type = entity_type

    class DynamicEntityAdmin(MetadataModelAdmin):
        entity_type = admin_entity_type
        list_display = ("name", "display_assigned", "modified_at")
        list_filter = ("assigned_user",)
        search_fields = ("name",)

        def get_queryset(self, request):
            queryset = super().get_queryset(request)
            return queryset.filter(entity_type=admin_entity_type)

        def save_model(self, request, obj, form, change):
            obj.entity_type = admin_entity_type
            super().save_model(request, obj, form, change)

        @display(description=_("Assigned"), ordering="assigned_user")
        def display_assigned(self, obj):
            return obj.assigned_user.name if obj.assigned_user else "-"

    DynamicEntityAdmin.__name__ = f"{entity_type}Admin"
    DynamicEntityAdmin.__qualname__ = f"{entity_type}Admin"
    return DynamicEntityAdmin


@admin.register(CustomEntity)
class CustomEntityAdmin(ModelAdmin):
    list_display = ("name", "label", "is_active", "modified_at")
    list_filter = ("is_active",)
    search_fields = ("name", "label", "description")
    readonly_fields = ("created_at", "modified_at")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "label",
                    "label_plural",
                    "template",
                    "is_active",
                    "description",
                )
            },
        ),
        (
            _("Menu"),
            {
                "fields": ("show_in_menu", "menu_order", "icon", "color"),
                "description": _(
                    "Icon is a Material Symbols name (e.g. extension, rocket_launch)."
                ),
            },
        ),
        (
            _("Behavior"),
            {
                "fields": (
                    "stream",
                    "show_in_calendar",
                    "sort_field",
                    "sort_direction",
                    "search_fields",
                    "duplicate_check_fields",
                )
            },
        ),
        (_("System"), {"fields": ("created_at", "modified_at")}),
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is not None and "template" not in readonly:
            readonly.append("template")
        return readonly
