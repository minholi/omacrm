from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from omacrm.core.models import CustomField, CustomLink, Layout


@admin.register(CustomField)
class CustomFieldAdmin(ModelAdmin):
    list_display = (
        "entity_type",
        "name",
        "field_type",
        "label",
        "required",
        "is_active",
        "order",
    )
    list_filter = ("entity_type", "field_type", "is_active")
    search_fields = ("entity_type", "name", "label")
    ordering = ("entity_type", "order", "name")
    readonly_fields = ("created_at", "modified_at")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    ("entity_type", "name"),
                    ("label", "field_type"),
                    ("required", "read_only"),
                    ("order", "is_active"),
                )
            },
        ),
        (
            _("Parameters"),
            {
                "fields": ("params",),
                "description": _(
                    "JSON parameters such as choices, default, max_length or tooltip."
                ),
            },
        ),
        (_("System"), {"fields": ("created_at", "modified_at")}),
    )


@admin.register(Layout)
class LayoutAdmin(ModelAdmin):
    list_display = ("entity_type", "layout_name", "is_custom", "modified_at")
    list_filter = ("entity_type", "layout_name", "is_custom")
    search_fields = ("entity_type", "layout_name")
    readonly_fields = ("created_at", "modified_at")
    fieldsets = (
        (None, {"fields": ("entity_type", "layout_name", "is_custom")}),
        (_("Layout data"), {"fields": ("data",)}),
        (_("System"), {"fields": ("created_at", "modified_at")}),
    )


@admin.register(CustomLink)
class CustomLinkAdmin(ModelAdmin):
    list_display = (
        "entity_type",
        "name",
        "link_type",
        "link_entity",
        "foreign_name",
        "is_active",
    )
    list_filter = ("entity_type", "link_type", "is_active")
    search_fields = ("entity_type", "name", "link_entity", "foreign_name")
    readonly_fields = ("created_at",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    ("entity_type", "name"),
                    ("link_type", "link_entity"),
                    ("foreign_name", "label_foreign"),
                    ("label", "is_active"),
                ),
                "description": _(
                    "The link is stored on both sides: `name` on this entity and "
                    "`foreign_name` on the target entity."
                ),
            },
        ),
        (_("System"), {"fields": ("created_at",)}),
    )
