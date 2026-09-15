from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from omacrm.core.admin.widgets import JSONEditorWidget
from omacrm.core.metadata.registry import registry
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
        (_("Parameters"), {"fields": ("params",)}),
        (_("System"), {"fields": ("created_at", "modified_at")}),
    )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change=change, **kwargs)
        form.base_fields["params"].widget = JSONEditorWidget(
            kind="custom_field",
            entity_field="entity_type",
            context_fields=("name", "field_type"),
            rows=8,
        )
        return form


@admin.register(Layout)
class LayoutAdmin(ModelAdmin):
    list_display = ("entity_type", "layout_name", "is_custom", "modified_at")
    list_filter = ("entity_type", "layout_name", "is_custom")
    search_fields = ("entity_type", "layout_name")
    readonly_fields = ("created_at", "modified_at", "editor_link")
    fieldsets = (
        (None, {"fields": ("entity_type", "layout_name", "is_custom")}),
        (_("Layout data"), {"fields": ("data", "editor_link")}),
        (_("System"), {"fields": ("created_at", "modified_at")}),
    )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change=change, **kwargs)
        form.base_fields["data"].widget = JSONEditorWidget(
            kind="layout",
            entity_field="entity_type",
            context_fields=("layout_name",),
            rows=12,
        )
        return form

    @admin.display(description=_("Layout editor"))
    def editor_link(self, obj):
        if obj is None or not obj.entity_type or not registry.has(obj.entity_type):
            return "-"
        url = reverse("layout_editor", kwargs={"entity_type": obj.entity_type})
        return format_html(
            '<a class="text-link" href="{}">{}</a>',
            url,
            _("Open in Layout Editor"),
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
