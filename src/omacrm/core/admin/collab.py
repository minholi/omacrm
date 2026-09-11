from django import forms
from django.contrib import admin, messages
from django.http import HttpResponse
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import action, display
from unfold.forms import BaseDialogForm
from unfold.widgets import UnfoldAdminSelectWidget

from omacrm.core.models import Attachment, Note, Notification
from omacrm.core.services.reactions import SUPPORTED_EMOJIS, toggle_reaction


class ReactionForm(BaseDialogForm):
    emoji = forms.ChoiceField(
        choices=[(emoji, emoji) for emoji in SUPPORTED_EMOJIS],
        label=_("Reaction"),
        widget=UnfoldAdminSelectWidget,
    )


@admin.register(Attachment)
class AttachmentAdmin(ModelAdmin):
    list_display = ("name", "file", "size", "created_by", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name",)
    readonly_fields = ("created_at", "size", "mime_type")


@admin.register(Note)
class NoteAdmin(ModelAdmin):
    list_display = (
        "type",
        "parent_display",
        "display_reactions",
        "created_by",
        "created_at",
        "is_internal",
    )
    list_filter = ("type", "is_internal")
    search_fields = ("post",)
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
    actions_row = ("react",)

    @display(description=_("Reactions"))
    def display_reactions(self, obj):
        return obj.reaction_summary or "-"

    @action(
        description=_("React"),
        icon="add_reaction",
        dialog={
            "title": _("React to note"),
            "description": _("Choose an emoji. Repeating the action removes it."),
            "form_class": ReactionForm,
            "form_submit_text": _("React"),
        },
    )
    def react(self, request, form, object_id):
        note = self.get_object(request, object_id)
        if note is None:
            messages.error(request, _("Note not found."))
        else:
            added = toggle_reaction(note, request.user, form.cleaned_data["emoji"])
            if added:
                messages.success(request, _("Reaction added."))
            else:
                messages.success(request, _("Reaction removed."))
        return HttpResponse(
            headers={"HX-Redirect": reverse("admin:core_note_changelist")}
        )


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
