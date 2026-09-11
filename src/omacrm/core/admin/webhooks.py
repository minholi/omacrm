from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from omacrm.core.models import Webhook, WebhookQueueItem


@admin.register(Webhook)
class WebhookAdmin(ModelAdmin):
    list_display = ("name", "entity_type", "event", "url", "is_active")
    list_filter = ("event", "entity_type", "is_active")
    search_fields = ("name", "entity_type", "url")
    readonly_fields = ("created_at", "modified_at")
    fieldsets = (
        (None, {"fields": ("name", "is_active")}),
        (_("Trigger"), {"fields": ("entity_type", "event", "url", "secret")}),
        (_("System"), {"fields": ("created_at", "modified_at")}),
    )


@admin.register(WebhookQueueItem)
class WebhookQueueItemAdmin(ModelAdmin):
    list_display = (
        "webhook",
        "status",
        "attempts",
        "response_code",
        "created_at",
        "delivered_at",
    )
    list_filter = ("status", "webhook")
    search_fields = ("webhook__name", "last_error")
    readonly_fields = (
        "webhook",
        "payload",
        "status",
        "attempts",
        "response_code",
        "last_error",
        "created_at",
        "delivered_at",
    )
