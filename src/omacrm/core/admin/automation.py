from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from omacrm.core.models import Formula, Workflow


@admin.register(Formula)
class FormulaAdmin(ModelAdmin):
    list_display = ("entity_type", "event", "description", "order", "is_active")
    list_filter = ("event", "entity_type", "is_active")
    search_fields = ("entity_type", "description", "script")
    ordering = ("entity_type", "event", "order")
    readonly_fields = ("created_at", "modified_at")
    fieldsets = (
        (
            None,
            {"fields": ("entity_type", "event", "description", "order", "is_active")},
        ),
        (
            _("Script"),
            {
                "fields": ("script",),
                "description": _(
                    "One statement per line. Assignments, e.g. "
                    "`probability = 50`, custom fields, e.g. "
                    "`custom.score = 10`, and calls, e.g. "
                    "`notify('Deal updated')` or `update('stage', 'Proposal')`."
                ),
            },
        ),
        (_("System"), {"fields": ("created_at", "modified_at")}),
    )


@admin.register(Workflow)
class WorkflowAdmin(ModelAdmin):
    list_display = ("name", "entity_type", "event", "is_active", "order")
    list_filter = ("event", "entity_type", "is_active")
    search_fields = ("name", "description", "entity_type")
    ordering = ("entity_type", "event", "order")
    readonly_fields = ("created_at", "modified_at")
    fieldsets = (
        (None, {"fields": ("name", "description", "is_active", "order")}),
        (_("Trigger"), {"fields": ("entity_type", "event", "condition")}),
        (
            _("Actions"),
            {
                "fields": ("actions",),
                "description": _(
                    'JSON list, e.g. [{"type": "set_field", "field": "priority", '
                    '"value": "High"}, {"type": "notify", "message": "Updated"}, '
                    '{"type": "send_email", "to": "email_address", '
                    '"subject": "Hi {{ name }}", "body": "<p>{{ name }}</p>"}, '
                    '{"type": "webhook", "webhook_id": 1}, '
                    '{"type": "update_related", "relation": "opportunities", '
                    '"fields": {"stage": "Closed Lost"}}].'
                ),
            },
        ),
        (_("System"), {"fields": ("created_at", "modified_at")}),
    )
