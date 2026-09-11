from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.widgets import UnfoldAdminPasswordToggleWidget

from omacrm.core.admin.base import MetadataModelAdmin
from omacrm.core.admin.inlines import AttachmentInline
from omacrm.core.models import Email, EmailAccount
from omacrm.core.services.jobs import schedule


@admin.register(Email)
class EmailAdmin(MetadataModelAdmin):
    entity_type = "Email"
    inlines = (AttachmentInline,)


class EmailAccountForm(forms.ModelForm):
    password = forms.CharField(
        required=False,
        label=_("Password"),
        widget=UnfoldAdminPasswordToggleWidget,
        help_text=_("Leave blank to keep the current password."),
    )

    class Meta:
        model = EmailAccount
        fields = (
            "name",
            "email_address",
            "imap_host",
            "imap_port",
            "imap_ssl",
            "imap_username",
            "folder",
            "unseen_only",
            "is_active",
            "default_assigned_user",
        )

    def save(self, commit=True):
        account = super().save(commit=False)
        raw = self.cleaned_data.get("password")
        if raw:
            account.set_password(raw)
        if commit:
            account.save()
        return account


@admin.register(EmailAccount)
class EmailAccountAdmin(ModelAdmin):
    form = EmailAccountForm
    list_display = ("name", "email_address", "imap_host", "is_active", "last_fetched_at")
    list_filter = ("is_active", "imap_ssl")
    search_fields = ("name", "email_address", "imap_host")
    readonly_fields = ("last_fetched_at", "created_at", "modified_at")
    autocomplete_fields = ("default_assigned_user",)
    fieldsets = (
        (None, {"fields": ("name", "email_address", "is_active")}),
        (
            _("IMAP"),
            {
                "fields": (
                    "imap_host",
                    "imap_port",
                    "imap_ssl",
                    "imap_username",
                    "password",
                    "folder",
                    "unseen_only",
                )
            },
        ),
        (_("Routing"), {"fields": ("default_assigned_user",)}),
        (_("System"), {"fields": ("last_fetched_at", "created_at", "modified_at")}),
    )
    actions = ("fetch_now",)

    @admin.action(description=_("Fetch now (enqueue job)"))
    def fetch_now(self, request, queryset):
        schedule("core.fetch_inbound_email")
        self.message_user(
            request,
            _("Inbound email fetch enqueued for active accounts."),
        )
