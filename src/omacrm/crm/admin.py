from django import forms
from django.contrib import admin, messages
from django.db import models
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from unfold.admin import GenericTabularInline, ModelAdmin, TabularInline
from unfold.decorators import action, display
from unfold.forms import BaseDialogForm
from unfold.contrib.forms.widgets import WysiwygWidget
from unfold.widgets import (
    UnfoldAdminSelect2Widget,
    UnfoldAdminSelectWidget,
    UnfoldAdminTextareaWidget,
    UnfoldBooleanSwitchWidget,
)

from omacrm.core.admin.base import MetadataModelAdmin
from omacrm.core.services.duplicates import DuplicateConflict
from omacrm.core.services.jobs import schedule
from omacrm.crm.models import (
    Account,
    AccountContact,
    Attendance,
    Call,
    Campaign,
    CampaignLogRecord,
    CampaignTrackingUrl,
    Case,
    Contact,
    Document,
    DocumentFolder,
    EmailQueueItem,
    EmailTemplate,
    KnowledgeBaseArticle,
    KnowledgeBaseCategory,
    Lead,
    LeadCapture,
    MassEmail,
    Meeting,
    Opportunity,
    OpportunityContact,
    TargetList,
    TargetListCategory,
    Task,
)
from omacrm.crm.services import LeadConversionService, send_email, send_invitations
from omacrm.crm.services.campaigns import record_bounce
from omacrm.crm.services.mass_email import build_queue
from omacrm.crm.services.target_lists import add_to_target_list

STAGE_LABELS = {
    "Prospecting": "info",
    "Qualification": "info",
    "Proposal": "primary",
    "Negotiation": "warning",
    "Closed Won": "success",
    "Closed Lost": "danger",
}

STATUS_LABELS = {
    "New": "info",
    "Assigned": "info",
    "In Process": "primary",
    "Converted": "success",
    "Recycled": "warning",
    "Dead": "danger",
}

TASK_STATUS_LABELS = {
    "Not Started": "info",
    "Started": "primary",
    "Completed": "success",
    "Canceled": "danger",
    "Deferred": "warning",
}

PRIORITY_LABELS = {
    "Low": "info",
    "Normal": "primary",
    "High": "warning",
    "Urgent": "danger",
}

EVENT_STATUS_LABELS = {
    "Planned": "info",
    "Held": "success",
    "Not Held": "danger",
}

CASE_STATUS_LABELS = {
    "New": "info",
    "Assigned": "info",
    "Pending": "warning",
    "Closed": "success",
    "Rejected": "danger",
    "Duplicate": "danger",
}

KB_STATUS_LABELS = {
    "Draft": "info",
    "In Review": "warning",
    "Published": "success",
    "Archived": "danger",
}

DOCUMENT_STATUS_LABELS = {
    "Draft": "info",
    "Active": "success",
    "Canceled": "danger",
    "Expired": "warning",
}


class SendEmailForm(BaseDialogForm):
    template = forms.ModelChoiceField(
        queryset=EmailTemplate.objects.none(),
        label=_("Template"),
        widget=UnfoldAdminSelect2Widget,
    )
    to_email = forms.EmailField(
        required=False,
        label=_("To"),
        help_text=_("Leave empty to use the record's email address."),
    )
    subject = forms.CharField(required=False, label=_("Subject override"))
    body = forms.CharField(
        required=False,
        label=_("Body override"),
        widget=UnfoldAdminTextareaWidget(attrs={"rows": 5}),
    )

    def __init__(self, request, object_id=None, *args, **kwargs):
        super().__init__(request, object_id=object_id, *args, **kwargs)
        self.fields["template"].queryset = EmailTemplate.objects.filter(is_active=True)


class EmailActionMixin:
    @action(
        description=_("Send Email"),
        icon="mail",
        variant="primary",
        dialog={
            "title": _("Send Email"),
            "description": _(
                "Choose a template. Use the overrides to customize the message."
            ),
            "form_class": SendEmailForm,
            "form_submit_text": _("Send"),
        },
    )
    def send_email_action(self, request, form, object_id):
        obj = self.get_object(request, object_id)
        if obj is None:
            messages.error(request, _("Record not found."))
            return HttpResponse(headers={"HX-Redirect": reverse("admin:index")})

        change_url = reverse(
            f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change", args=[obj.pk]
        )
        try:
            send_email(
                obj,
                template=form.cleaned_data.get("template"),
                to_email=form.cleaned_data.get("to_email") or None,
                subject=form.cleaned_data.get("subject") or None,
                body=form.cleaned_data.get("body") or None,
                user=request.user,
            )
        except Exception as exc:  # noqa: BLE001 - surface delivery errors in the UI
            messages.error(request, str(exc))
        else:
            messages.success(request, _("Email sent."))
        return HttpResponse(headers={"HX-Redirect": change_url})


class TargetListMembershipForm(BaseDialogForm):
    target_list = forms.ModelChoiceField(
        queryset=TargetList.objects.none(),
        label=_("Target List"),
        widget=UnfoldAdminSelect2Widget,
    )
    opted_out = forms.BooleanField(
        required=False, label=_("Opted out"), widget=UnfoldBooleanSwitchWidget
    )

    def __init__(self, request, object_id=None, *args, **kwargs):
        super().__init__(request, object_id=object_id, *args, **kwargs)
        self.fields["target_list"].queryset = TargetList.objects.all()


class TargetListActionMixin:
    @action(
        description=_("Add to Target List"),
        icon="playlist_add",
        dialog={
            "title": _("Add to Target List"),
            "description": _("Add the record to a target list or mark it as opted out."),
            "form_class": TargetListMembershipForm,
            "form_submit_text": _("Save"),
        },
    )
    def add_to_target_list_action(self, request, form, object_id):
        obj = self.get_object(request, object_id)
        if obj is None:
            messages.error(request, _("Record not found."))
            return HttpResponse(headers={"HX-Redirect": reverse("admin:index")})

        add_to_target_list(
            obj,
            form.cleaned_data["target_list"],
            opted_out=form.cleaned_data.get("opted_out", False),
        )
        messages.success(request, _("Target list updated."))
        return HttpResponse(
            headers={
                "HX-Redirect": reverse(
                    f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change",
                    args=[obj.pk],
                )
            }
        )



class AccountContactInline(TabularInline):
    model = AccountContact
    fk_name = "account"
    extra = 0
    autocomplete_fields = ("contact",)
    fields = ("contact", "role", "is_inactive")


class ContactAccountInline(TabularInline):
    model = AccountContact
    fk_name = "contact"
    extra = 0
    autocomplete_fields = ("account",)
    fields = ("account", "role", "is_inactive")


class OpportunityContactInline(TabularInline):
    model = OpportunityContact
    extra = 0
    autocomplete_fields = ("contact",)
    fields = ("contact", "role")


@admin.register(Account)
class AccountAdmin(EmailActionMixin, TargetListActionMixin, MetadataModelAdmin):
    entity_type = "Account"
    actions_detail = ("add_note", "send_email_action", "add_to_target_list_action")
    list_display = ("display_name", "type", "industry", "phone_number", "display_assigned")
    list_filter = ("type", "industry", "assigned_user")
    search_fields = ("name", "email_address", "phone_number", "website")
    autocomplete_fields = ("assigned_user",)
    inlines = (AccountContactInline,)

    @display(description=_("Name"), ordering="name", header=True)
    def display_name(self, obj):
        return [obj.name, obj.email_address or obj.phone_number, obj.name[:2].upper()]

    @display(description=_("Assigned"), ordering="assigned_user")
    def display_assigned(self, obj):
        return obj.assigned_user.name if obj.assigned_user else "-"


@admin.register(Contact)
class ContactAdmin(EmailActionMixin, TargetListActionMixin, MetadataModelAdmin):
    entity_type = "Contact"
    actions_detail = ("add_note", "send_email_action", "add_to_target_list_action")
    list_display = (
        "display_name",
        "account",
        "email_address",
        "phone_number",
        "display_assigned",
    )
    list_filter = ("account", "do_not_call", "assigned_user")
    search_fields = ("name", "email_address", "phone_number", "title")
    autocomplete_fields = ("account", "assigned_user")
    inlines = (ContactAccountInline,)

    @display(description=_("Name"), ordering="name", header=True)
    def display_name(self, obj):
        subtitle = obj.title or obj.email_address or obj.phone_number
        return [obj.name, subtitle, (obj.name or "?")[:2].upper()]

    @display(description=_("Assigned"), ordering="assigned_user")
    def display_assigned(self, obj):
        return obj.assigned_user.name if obj.assigned_user else "-"


class LeadConvertForm(BaseDialogForm):
    create_account = forms.BooleanField(
        required=False,
        initial=True,
        label=_("Create Account"),
        widget=UnfoldBooleanSwitchWidget,
    )
    create_contact = forms.BooleanField(
        required=False,
        initial=True,
        label=_("Create Contact"),
        widget=UnfoldBooleanSwitchWidget,
    )
    create_opportunity = forms.BooleanField(
        required=False,
        initial=True,
        label=_("Create Opportunity"),
        widget=UnfoldBooleanSwitchWidget,
    )


@admin.register(Lead)
class LeadAdmin(EmailActionMixin, TargetListActionMixin, MetadataModelAdmin):
    entity_type = "Lead"
    list_display = (
        "display_name",
        "display_status",
        "source",
        "email_address",
        "display_assigned",
    )
    list_filter = ("status", "source", "industry", "assigned_user")
    search_fields = ("name", "email_address", "phone_number", "account_name")
    autocomplete_fields = ("assigned_user",)
    actions_detail = ("add_note", "convert_lead", "send_email_action", "add_to_target_list_action")

    @display(description=_("Name"), ordering="name", header=True)
    def display_name(self, obj):
        subtitle = obj.account_name or obj.email_address or obj.phone_number
        return [obj.name, subtitle, (obj.name or "?")[:2].upper()]

    @display(description=_("Status"), ordering="status", label=STATUS_LABELS)
    def display_status(self, obj):
        return obj.status, obj.get_status_display()

    @display(description=_("Assigned"), ordering="assigned_user")
    def display_assigned(self, obj):
        return obj.assigned_user.name if obj.assigned_user else "-"

    @action(
        description=_("Convert Lead"),
        icon="swap_horiz",
        variant="primary",
        dialog={
            "title": _("Convert Lead"),
            "description": _(
                "The lead will be converted into the selected records using the "
                "values already filled in."
            ),
            "form_class": LeadConvertForm,
            "form_submit_text": _("Convert"),
        },
    )
    def convert_lead(self, request, form, object_id):
        lead = self.get_object(request, object_id)
        if lead is None:
            messages.error(request, _("Lead not found."))
            return HttpResponse(
                headers={"HX-Redirect": reverse("admin:crm_lead_changelist")}
            )
        if not self.has_change_permission(request, lead):
            messages.error(request, _("You do not have permission to convert this lead."))
            return HttpResponse(
                headers={"HX-Redirect": reverse("admin:crm_lead_change", args=[lead.pk])}
            )

        service = LeadConversionService(request.user)
        values = service.get_convert_data(lead)
        data = {}
        if form.cleaned_data.get("create_account") and values["Account"].get("name"):
            data["Account"] = values["Account"]
        if form.cleaned_data.get("create_contact") and values["Contact"].get("last_name"):
            data["Contact"] = values["Contact"]
        if form.cleaned_data.get("create_opportunity") and values["Opportunity"].get("name"):
            data["Opportunity"] = values["Opportunity"]

        if not data:
            messages.warning(request, _("Nothing selected to create."))
            return HttpResponse(
                headers={"HX-Redirect": reverse("admin:crm_lead_change", args=[lead.pk])}
            )

        try:
            created = service.convert(lead, data)
        except DuplicateConflict as exc:
            messages.error(request, str(exc))
            return HttpResponse(
                headers={"HX-Redirect": reverse("admin:crm_lead_change", args=[lead.pk])}
            )

        target = (
            created.get("Opportunity")
            or created.get("Account")
            or created.get("Contact")
        )
        if target is not None:
            url = reverse(
                f"admin:crm_{target._meta.model_name}_change", args=[target.pk]
            )
        else:
            url = reverse("admin:crm_lead_change", args=[lead.pk])
        messages.success(request, _("Lead converted."))
        return HttpResponse(headers={"HX-Redirect": url})


@admin.register(Opportunity)
class OpportunityAdmin(MetadataModelAdmin):
    entity_type = "Opportunity"
    list_display = (
        "name",
        "account",
        "display_stage",
        "display_amount",
        "probability",
        "close_date",
        "display_assigned",
    )
    list_filter = ("stage", "lead_source", "account", "assigned_user")
    search_fields = ("name", "account__name", "contact__name")
    autocomplete_fields = ("account", "contact", "assigned_user")
    inlines = (OpportunityContactInline,)

    @display(description=_("Stage"), ordering="stage", label=STAGE_LABELS)
    def display_stage(self, obj):
        return obj.stage, obj.get_stage_display()

    @display(description=_("Amount"), ordering="amount", formatting="price")
    def display_amount(self, obj):
        if obj.amount is None:
            return None
        return obj.amount.amount if hasattr(obj.amount, "amount") else obj.amount

    @display(description=_("Assigned"), ordering="assigned_user")
    def display_assigned(self, obj):
        return obj.assigned_user.name if obj.assigned_user else "-"


@admin.register(Task)
class TaskAdmin(MetadataModelAdmin):
    entity_type = "Task"
    list_display = (
        "name",
        "display_status",
        "display_priority",
        "date_end",
        "display_assigned",
    )
    list_filter = ("status", "priority", "assigned_user")
    search_fields = ("name", "description")
    autocomplete_fields = ("account", "contact", "assigned_user")

    @display(description=_("Status"), ordering="status", label=TASK_STATUS_LABELS)
    def display_status(self, obj):
        return obj.status, obj.get_status_display()

    @display(description=_("Priority"), ordering="priority", label=PRIORITY_LABELS)
    def display_priority(self, obj):
        return obj.priority, obj.get_priority_display()

    @display(description=_("Assigned"), ordering="assigned_user")
    def display_assigned(self, obj):
        return obj.assigned_user.name if obj.assigned_user else "-"


class AttendanceInline(GenericTabularInline):
    model = Attendance
    ct_field = "event_type"
    ct_fk_field = "event_id"
    extra = 0
    autocomplete_fields = ("user", "contact", "lead")
    fields = ("user", "contact", "lead", "status", "invitation_sent_at")
    readonly_fields = ("invitation_sent_at",)


class EventInvitationMixin:
    actions = MetadataModelAdmin.actions + ("send_invitations_action",)
    inlines = (AttendanceInline,)

    @admin.action(description=_("Send invitations"))
    def send_invitations_action(self, request, queryset):
        base_url = request.build_absolute_uri("/").rstrip("/")
        total = sum(send_invitations(event, base_url=base_url) for event in queryset)
        self.message_user(
            request,
            _("%(count)s invitation(s) sent.") % {"count": total},
            level=messages.SUCCESS,
        )


@admin.register(Call)
class CallAdmin(EventInvitationMixin, MetadataModelAdmin):
    entity_type = "Call"
    list_display = (
        "name",
        "display_status",
        "date_start",
        "direction",
        "display_assigned",
    )
    list_filter = ("status", "direction", "assigned_user")
    search_fields = ("name", "description")
    autocomplete_fields = ("account", "assigned_user")

    @display(description=_("Status"), ordering="status", label=EVENT_STATUS_LABELS)
    def display_status(self, obj):
        return obj.status, obj.get_status_display()

    @display(description=_("Assigned"), ordering="assigned_user")
    def display_assigned(self, obj):
        return obj.assigned_user.name if obj.assigned_user else "-"


@admin.register(Meeting)
class MeetingAdmin(
    EventInvitationMixin, MetadataModelAdmin
):
    entity_type = "Meeting"
    list_display = (
        "name",
        "display_status",
        "date_start",
        "is_all_day",
        "display_assigned",
    )
    list_filter = ("status", "is_all_day", "assigned_user")
    search_fields = ("name", "description")
    autocomplete_fields = ("account", "assigned_user")

    @display(description=_("Status"), ordering="status", label=EVENT_STATUS_LABELS)
    def display_status(self, obj):
        return obj.status, obj.get_status_display()

    @display(description=_("Assigned"), ordering="assigned_user")
    def display_assigned(self, obj):
        return obj.assigned_user.name if obj.assigned_user else "-"


class CaseAdminMixin:
    @display(description=_("Status"), ordering="status", label=CASE_STATUS_LABELS)
    def display_status(self, obj):
        return obj.status, obj.get_status_display()

    @display(description=_("Priority"), ordering="priority", label=PRIORITY_LABELS)
    def display_priority(self, obj):
        return obj.priority, obj.get_priority_display()

    @display(description=_("Assigned"), ordering="assigned_user")
    def display_assigned(self, obj):
        return obj.assigned_user.name if obj.assigned_user else "-"


@admin.register(Case)
class CaseAdmin(CaseAdminMixin, MetadataModelAdmin):
    entity_type = "Case"
    list_display = (
        "number",
        "name",
        "display_status",
        "display_priority",
        "type",
        "display_assigned",
    )
    list_filter = ("status", "priority", "type", "account", "assigned_user")
    search_fields = ("name", "description", "number")
    autocomplete_fields = ("account", "contact", "lead", "assigned_user")


@admin.register(KnowledgeBaseCategory)
class KnowledgeBaseCategoryAdmin(ModelAdmin):
    list_display = ("name", "order", "parent")
    search_fields = ("name",)
    autocomplete_fields = ("parent",)


@admin.register(KnowledgeBaseArticle)
class KnowledgeBaseArticleAdmin(MetadataModelAdmin):
    entity_type = "KnowledgeBaseArticle"
    formfield_overrides = {models.TextField: {"widget": WysiwygWidget}}
    list_display = (
        "name",
        "display_status",
        "language",
        "publish_date",
        "expiration_date",
        "order",
    )
    list_filter = ("status", "language", "categories", "assigned_user")
    search_fields = ("name", "body", "description")
    autocomplete_fields = ("categories", "assigned_user")
    ordering_field = "order"

    @display(description=_("Status"), ordering="status", label=KB_STATUS_LABELS)
    def display_status(self, obj):
        return obj.status, obj.get_status_display()


@admin.register(DocumentFolder)
class DocumentFolderAdmin(ModelAdmin):
    list_display = ("name", "order", "parent")
    search_fields = ("name",)
    autocomplete_fields = ("parent",)


@admin.register(Document)
class DocumentAdmin(MetadataModelAdmin):
    entity_type = "Document"
    list_display = (
        "name",
        "display_status",
        "type",
        "folder",
        "publish_date",
        "expiration_date",
    )
    list_filter = ("status", "type", "folder", "assigned_user")
    search_fields = ("name", "description")
    autocomplete_fields = (
        "folder",
        "accounts",
        "contacts",
        "leads",
        "opportunities",
        "assigned_user",
    )

    @display(description=_("Status"), ordering="status", label=DOCUMENT_STATUS_LABELS)
    def display_status(self, obj):
        return obj.status, obj.get_status_display()


@admin.register(EmailTemplate)
class EmailTemplateAdmin(ModelAdmin):
    list_display = ("name", "subject", "is_active", "modified_at")
    list_filter = ("is_active",)
    search_fields = ("name", "subject")
    readonly_fields = ("created_at", "modified_at")
    actions_detail = ("open_designer",)
    fieldsets = (
        (None, {"fields": ("name", "subject", "is_active")}),
        (
            _("Body"),
            {
                "fields": ("body",),
                "description": _(
                    "Prefer the Design action for rich emails; the raw HTML field "
                    "is kept for advanced or legacy templates."
                ),
            },
        ),
        (_("System"), {"fields": ("created_at", "modified_at")}),
    )

    @action(description=_("Design"), icon="palette", variant="primary")
    def open_designer(self, request, object_id):
        return redirect("email_template_design", pk=object_id)


CAMPAIGN_STATUS_LABELS = {
    "Planning": "info",
    "Active": "success",
    "Inactive": "warning",
    "Complete": "primary",
}

MASS_EMAIL_STATUS_LABELS = {
    "Draft": "info",
    "Pending": "warning",
    "In Process": "primary",
    "Complete": "success",
    "Failed": "danger",
}


@admin.register(TargetListCategory)
class TargetListCategoryAdmin(ModelAdmin):
    list_display = ("name", "order", "parent")
    search_fields = ("name",)
    autocomplete_fields = ("parent",)


@admin.register(TargetList)
class TargetListAdmin(MetadataModelAdmin):
    entity_type = "TargetList"
    list_display = ("name", "category", "display_entry_count", "display_opted_out")
    list_filter = ("category", "assigned_user")
    search_fields = ("name", "description")
    autocomplete_fields = ("category", "assigned_user")

    @display(description=_("Entries"))
    def display_entry_count(self, obj):
        return obj.entry_count

    @display(description=_("Opted Out"))
    def display_opted_out(self, obj):
        return obj.opted_out_count


class CampaignTrackingUrlInline(TabularInline):
    model = CampaignTrackingUrl
    extra = 0
    fields = ("name", "url", "action", "message")


@admin.register(Campaign)
class CampaignAdmin(MetadataModelAdmin):
    entity_type = "Campaign"
    list_display = ("name", "display_status", "type", "start_date", "end_date")
    list_filter = ("status", "type", "assigned_user")
    search_fields = ("name", "description")
    autocomplete_fields = ("target_lists", "assigned_user")
    inlines = (CampaignTrackingUrlInline,)

    @display(description=_("Status"), ordering="status", label=CAMPAIGN_STATUS_LABELS)
    def display_status(self, obj):
        return obj.status, obj.get_status_display()


@admin.register(CampaignTrackingUrl)
class CampaignTrackingUrlAdmin(ModelAdmin):
    list_display = ("name", "campaign", "action", "url")
    list_filter = ("action", "campaign")
    search_fields = ("name", "url")
    autocomplete_fields = ("campaign",)


@admin.register(CampaignLogRecord)
class CampaignLogRecordAdmin(ModelAdmin):
    list_display = ("campaign", "action", "action_date", "entity")
    list_filter = ("action", "campaign")
    date_hierarchy = "action_date"
    readonly_fields = ("campaign", "action", "action_date", "entity_type", "entity_id", "data")


@admin.register(MassEmail)
class MassEmailAdmin(MetadataModelAdmin):
    entity_type = "MassEmail"
    list_display = ("name", "display_status", "campaign", "start_at")
    list_filter = ("status", "campaign", "assigned_user")
    search_fields = ("name",)
    autocomplete_fields = ("email_template", "campaign", "target_lists", "assigned_user")
    actions_detail = ("add_note", "build_and_send")

    @display(description=_("Status"), ordering="status", label=MASS_EMAIL_STATUS_LABELS)
    def display_status(self, obj):
        return obj.status, obj.get_status_display()

    @action(
        description=_("Build queue and send"),
        icon="send",
        variant="primary",
        dialog={
            "title": _("Build queue and send"),
            "description": _(
                "The queue is rebuilt from the selected target lists (opted-out "
                "entries are skipped) and processed in the background."
            ),
            "form_submit_text": _("Build and send"),
        },
    )
    def build_and_send(self, request, form, object_id):
        mass_email = self.get_object(request, object_id)
        if mass_email is None:
            messages.error(request, _("Mass email not found."))
            return HttpResponse(headers={"HX-Redirect": reverse("admin:index")})

        count = build_queue(mass_email)
        if count:
            schedule(
                "crm.process_mass_email",
                data={"mass_email_id": mass_email.pk},
                name=f"Mass email: {mass_email.name}",
            )
            messages.success(request, _("%(count)s message(s) queued.") % {"count": count})
        else:
            messages.warning(request, _("No recipients found in the target lists."))

        return HttpResponse(
            headers={
                "HX-Redirect": reverse(
                    "admin:crm_massemail_change", args=[mass_email.pk]
                )
            }
        )


@admin.register(EmailQueueItem)
class EmailQueueItemAdmin(ModelAdmin):
    list_display = ("email_address", "mass_email", "status", "attempt_count", "sent_at")
    list_filter = ("status", "mass_email")
    search_fields = ("email_address",)
    readonly_fields = ("mass_email", "entity_type", "entity_id", "email_address", "attempt_count", "last_error", "sent_at", "created_at")
    actions = ("mark_bounced_hard", "mark_bounced_soft")

    @admin.action(description=_("Mark as bounced (hard)"))
    def mark_bounced_hard(self, request, queryset):
        for item in queryset:
            record_bounce(item, "Hard")
        self.message_user(
            request, _("Selected items marked as hard bounces."), level=messages.SUCCESS
        )

    @admin.action(description=_("Mark as bounced (soft)"))
    def mark_bounced_soft(self, request, queryset):
        for item in queryset:
            record_bounce(item, "Soft")
        self.message_user(
            request, _("Selected items marked as soft bounces."), level=messages.SUCCESS
        )


@admin.register(LeadCapture)
class LeadCaptureAdmin(ModelAdmin):
    list_display = ("name", "is_active", "campaign", "target_list", "source")
    list_filter = ("is_active", "campaign", "target_list")
    search_fields = ("name", "api_key")
    readonly_fields = ("api_key", "created_at", "modified_at")
    autocomplete_fields = ("campaign", "target_list", "default_assigned_user")
    fieldsets = (
        (None, {"fields": ("name", "is_active", "api_key")}),
        (_("Routing"), {"fields": ("campaign", "target_list", "source", "default_assigned_user")}),
        (
            _("Form"),
            {
                "fields": (
                    "field_list",
                    "opt_in_confirmation",
                    "opt_in_template",
                    "opt_in_lifetime_hours",
                )
            },
        ),
        (_("System"), {"fields": ("created_at", "modified_at")}),
    )
