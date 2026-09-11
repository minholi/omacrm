from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline

from omacrm.core.models import Job, ScheduledJob, ScheduledJobLog
from omacrm.core.services.jobs import JobRunner, schedule


@admin.register(Job)
class JobAdmin(ModelAdmin):
    list_display = (
        "name",
        "class_name",
        "status",
        "queue",
        "execute_time",
        "attempts",
        "created_at",
    )
    list_filter = ("status", "queue")
    search_fields = ("name", "class_name")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "started_at", "finished_at", "last_error", "attempts")
    actions = ("run_now",)

    @admin.action(description=_("Run selected jobs now"))
    def run_now(self, request, queryset):
        for job in queryset:
            JobRunner.run_job(job)
        self.message_user(request, _("Selected jobs executed."))


class ScheduledJobLogInline(TabularInline):
    model = ScheduledJobLog
    extra = 0
    fields = ("status", "message", "created_at")
    readonly_fields = ("status", "message", "created_at")
    can_delete = False


@admin.register(ScheduledJob)
class ScheduledJobAdmin(ModelAdmin):
    list_display = ("name", "job", "scheduling", "is_active", "last_run", "last_status")
    list_filter = ("is_active",)
    search_fields = ("name", "job")
    inlines = (ScheduledJobLogInline,)
    actions = ("run_now",)

    @admin.action(description=_("Enqueue selected scheduled jobs now"))
    def run_now(self, request, queryset):
        for scheduled_job in queryset:
            schedule(scheduled_job.job, data=scheduled_job.data, name=scheduled_job.name)
        self.message_user(request, _("Selected jobs enqueued."))
