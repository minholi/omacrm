from django.contrib import admin
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from omacrm.core.admin.widgets import JSONEditorWidget, ScriptEditorWidget
from omacrm.core.models import DynamicLogic, Formula, Workflow, WorkflowRun
from omacrm.core.services.workflow_diagram import build_flow


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
            {"fields": ("script",)},
        ),
        (_("System"), {"fields": ("created_at", "modified_at")}),
    )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change=change, **kwargs)
        form.base_fields["script"].widget = ScriptEditorWidget(
            kind="formula", entity_field="entity_type", rows=14
        )
        return form


@admin.register(DynamicLogic)
class DynamicLogicAdmin(ModelAdmin):
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

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change=change, **kwargs)
        form.base_fields["condition"].widget = JSONEditorWidget(
            kind="dynamic_logic", entity_field="entity_type", rows=12
        )
        return form


@admin.register(Workflow)
class WorkflowAdmin(ModelAdmin):
    list_display = ("name", "entity_type", "event", "is_active", "order")
    list_filter = ("event", "entity_type", "is_active")
    search_fields = ("name", "description", "entity_type")
    ordering = ("entity_type", "event", "order")
    readonly_fields = ("created_at", "modified_at", "flow_preview")
    fieldsets = (
        (None, {"fields": ("name", "description", "is_active", "order")}),
        (_("Trigger"), {"fields": ("entity_type", "event", "condition")}),
        (_("Actions"), {"fields": ("actions",)}),
        (_("Flow"), {"fields": ("flow_preview",)}),
        (_("System"), {"fields": ("created_at", "modified_at")}),
    )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change=change, **kwargs)
        form.base_fields["condition"].widget = ScriptEditorWidget(
            kind="formula", entity_field="entity_type", rows=3
        )
        form.base_fields["actions"].widget = JSONEditorWidget(
            kind="workflow_actions", entity_field="entity_type", rows=16
        )
        return form

    @admin.display(description=_("Flow"))
    def flow_preview(self, obj):
        if obj is None or not obj.pk:
            return _("Save the rule to preview the flow.")
        from omacrm.core.services.workflows import compile_actions

        nodes = build_flow(compile_actions(obj.actions or []))
        return mark_safe(
            render_to_string("admin/workflow_flow.html", {"nodes": nodes})
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
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "workflow",
                    "entity_type",
                    "record_id",
                    "status",
                    "cursor",
                    "execute_time",
                    "wait_deadline",
                    "last_error",
                    "created_at",
                    "finished_at",
                )
            },
        ),
        (_("Flow"), {"fields": ("flow_view",)}),
        (_("Program"), {"fields": ("program", "trace", "context")}),
    )
    readonly_fields = (
        "workflow",
        "entity_type",
        "record_id",
        "status",
        "cursor",
        "program",
        "trace",
        "context",
        "execute_time",
        "wait_deadline",
        "last_error",
        "created_at",
        "finished_at",
        "flow_view",
    )
    actions = ("resume_now", "retry_failed", "cancel_runs")

    @admin.display(description=_("Flow"))
    def flow_view(self, obj):
        if obj is None or not obj.pk:
            return ""
        return mark_safe(
            render_to_string(
                "admin/workflow_flow.html",
                {"nodes": build_flow(obj.program, obj)},
            )
        )

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
