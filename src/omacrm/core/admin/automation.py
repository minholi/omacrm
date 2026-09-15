from django.contrib import admin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.widgets import UnfoldAdminTextareaWidget

from omacrm.core.models import DynamicLogic, Formula, Workflow, WorkflowRun


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


@admin.register(DynamicLogic)
class DynamicLogicAdmin(ModelAdmin):
    formfield_overrides = {
        models.JSONField: {
            "widget": UnfoldAdminTextareaWidget(attrs={"rows": 10})
        }
    }
    list_display = ("entity_type", "field_name", "action", "is_active")
    list_filter = ("action", "entity_type", "is_active")
    search_fields = ("entity_type", "field_name")
    ordering = ("entity_type", "field_name", "action")
    readonly_fields = ("created_at", "modified_at")
    fieldsets = (
        (
            None,
            {"fields": ("entity_type", "field_name", "action", "is_active")},
        ),
        (_("Condition"), {"fields": ("condition",)}),
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
                    '"fields": {"stage": "Closed Lost"}}]. Steps: '
                    '{"type": "wait", "duration": "3d"} or '
                    '{"type": "wait", "until_date_field": "date_end"} or '
                    '{"type": "wait", "until_condition": "status == \'Completed\'", '
                    '"poll_interval": "1h", "timeout": "30d"} pauses the rule '
                    '(resumed by the "Resume waiting workflow runs" scheduled '
                    'job); {"type": "branch", "condition": "stage == \'Proposal\'", '
                    '"then": [...], "else": [...]} routes the steps.'
                ),
            },
        ),
        (_("System"), {"fields": ("created_at", "modified_at")}),
    )


@admin.register(WorkflowRun)
class WorkflowRunAdmin(ModelAdmin):
    list_display = (
        "id",
        "workflow",
        "entity_type",
        "record_id",
        "status",
        "cursor",
        "execute_time",
        "created_at",
    )
    list_filter = ("status", "workflow", "entity_type")
    search_fields = ("entity_type", "last_error", "workflow__name")
    ordering = ("-created_at",)
    readonly_fields = (
        "workflow",
        "entity_type",
        "record_id",
        "status",
        "cursor",
        "program",
        "context",
        "execute_time",
        "wait_deadline",
        "last_error",
        "created_at",
        "finished_at",
    )
    actions = ("resume_now", "retry_failed", "cancel_runs")

    @admin.action(description=_("Resume selected runs now"))
    def resume_now(self, request, queryset):
        from omacrm.core.services import workflows

        resumed = 0
        for run in queryset.filter(
            status__in=[WorkflowRun.Status.RUNNING, WorkflowRun.Status.WAITING]
        ):
            workflows.advance(run)
            resumed += 1
        self.message_user(request, _("%(count)s run(s) resumed.") % {"count": resumed})

    @admin.action(description=_("Retry selected failed runs"))
    def retry_failed(self, request, queryset):
        from omacrm.core.services import workflows

        retried = 0
        for run in queryset.filter(status=WorkflowRun.Status.FAILED):
            run.status = WorkflowRun.Status.RUNNING
            run.last_error = ""
            run.finished_at = None
            run.save(update_fields=["status", "last_error", "finished_at"])
            workflows.advance(run)
            retried += 1
        self.message_user(request, _("%(count)s run(s) retried.") % {"count": retried})

    @admin.action(description=_("Cancel selected runs"))
    def cancel_runs(self, request, queryset):
        cancelled = queryset.filter(
            status__in=[WorkflowRun.Status.RUNNING, WorkflowRun.Status.WAITING]
        ).update(
            status=WorkflowRun.Status.CANCELLED,
            execute_time=None,
            wait_deadline=None,
            finished_at=timezone.now(),
        )
        self.message_user(request, _("%(count)s run(s) cancelled.") % {"count": cancelled})
