from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from omacrm.core.models import Attachment, Note, Notification


@admin.register(Attachment)
class AttachmentAdmin(ModelAdmin):
    list_display = ("name", "file", "size", "created_by", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name",)
    readonly_fields = ("created_at", "size", "mime_type")


@admin.register(Note)
class NoteAdmin(ModelAdmin):
    list_display = ("type", "parent_display", "created_by", "created_at", "is_internal")
    list_filter = ("type", "is_internal")
    search_fields = ("post",)
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ("user", "type", "message", "read", "created_at")
    list_filter = ("type", "read")
    search_fields = ("message", "user__user_name")
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
    actions = ("mark_as_read",)

    @admin.action(description=_("Mark selected notifications as read"))
    def mark_as_read(self, request, queryset):
        updated = queryset.update(read=True)
        self.message_user(request, _("%(count)s notification(s) marked as read.") % {"count": updated})
