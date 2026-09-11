import secrets

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from omacrm.core.models import BaseEntity, CustomDataMixin
from omacrm.crm.models.email import EmailTemplate


class TargetListCategory(CustomDataMixin, models.Model):
    name = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=100)
    description = models.TextField(blank=True, default="")
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "target list categories"

    def __str__(self):
        return self.name


class TargetList(BaseEntity):
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True, default="")
    category = models.ForeignKey(
        TargetListCategory,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="target_lists",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def entry_count(self):
        return self.members.count()

    @property
    def opted_out_count(self):
        return self.members.filter(opted_out=True).count()


class TargetListMember(models.Model):
    target_list = models.ForeignKey(
        TargetList, on_delete=models.CASCADE, related_name="members"
    )
    entity_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="+"
    )
    entity_id = models.PositiveBigIntegerField()
    entity = GenericForeignKey("entity_type", "entity_id")
    opted_out = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("target_list", "entity_type", "entity_id")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.entity} @ {self.target_list}"


class Campaign(BaseEntity):
    class Status(models.TextChoices):
        PLANNING = "Planning", _("Planning")
        ACTIVE = "Active", _("Active")
        INACTIVE = "Inactive", _("Inactive")
        COMPLETE = "Complete", _("Complete")

    class Type(models.TextChoices):
        EMAIL = "Email", _("Email")
        NEWSLETTER = "Newsletter", _("Newsletter")
        INFORMATIONAL_EMAIL = "Informational Email", _("Informational Email")
        WEB = "Web", _("Web")
        TELEVISION = "Television", _("Television")
        RADIO = "Radio", _("Radio")
        MAIL = "Mail", _("Mail")

    name = models.CharField(max_length=255, db_index=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PLANNING
    )
    type = models.CharField(max_length=30, choices=Type.choices, default=Type.EMAIL)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True, default="")
    target_lists = models.ManyToManyField(
        TargetList, blank=True, related_name="campaigns"
    )
    sent_count = models.PositiveIntegerField(default=0)
    opened_count = models.PositiveIntegerField(default=0)
    clicked_count = models.PositiveIntegerField(default=0)
    opted_out_count = models.PositiveIntegerField(default=0)
    bounced_count = models.PositiveIntegerField(default=0)
    revenue = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class CampaignTrackingUrl(models.Model):
    class Action(models.TextChoices):
        REDIRECT = "Redirect", _("Redirect")
        SHOW_MESSAGE = "Show Message", _("Show Message")

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="tracking_urls"
    )
    name = models.CharField(max_length=255)
    url = models.URLField(blank=True, default="")
    action = models.CharField(
        max_length=20, choices=Action.choices, default=Action.REDIRECT
    )
    message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def url_to_use(self):
        from django.urls import reverse

        return reverse("campaign_track_click", args=[self.pk])


class CampaignLogRecord(models.Model):
    class Action(models.TextChoices):
        SENT = "Sent", _("Sent")
        OPENED = "Opened", _("Opened")
        CLICKED = "Clicked", _("Clicked")
        OPTED_OUT = "Opted Out", _("Opted Out")
        BOUNCED = "Bounced", _("Bounced")
        LEAD_CREATED = "Lead Created", _("Lead Created")

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="log_records"
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    bounced_type = models.CharField(
        max_length=10,
        choices=[("Hard", "Hard"), ("Soft", "Soft")],
        blank=True,
        default="",
    )
    action_date = models.DateTimeField(default=timezone.now)
    entity_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    entity_id = models.PositiveBigIntegerField(null=True, blank=True)
    entity = GenericForeignKey("entity_type", "entity_id")
    data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-action_date"]

    def __str__(self):
        return f"{self.action} ({self.campaign})"


class MassEmail(BaseEntity):
    class Status(models.TextChoices):
        DRAFT = "Draft", _("Draft")
        PENDING = "Pending", _("Pending")
        IN_PROCESS = "In Process", _("In Process")
        COMPLETE = "Complete", _("Complete")
        FAILED = "Failed", _("Failed")

    name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    from_name = models.CharField(max_length=255, blank=True, default="")
    from_address = models.EmailField(blank=True, default="")
    reply_to_address = models.EmailField(blank=True, default="")
    start_at = models.DateTimeField(null=True, blank=True)
    email_template = models.ForeignKey(
        EmailTemplate,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mass_emails",
    )
    campaign = models.ForeignKey(
        Campaign,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mass_emails",
    )
    target_lists = models.ManyToManyField(
        TargetList, blank=True, related_name="mass_emails"
    )
    opt_out_entirely = models.BooleanField(default=False)
    store_sent_emails = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "mass emails"

    def __str__(self):
        return self.name


class EmailQueueItem(models.Model):
    class Status(models.TextChoices):
        PENDING = "Pending", _("Pending")
        SENT = "Sent", _("Sent")
        FAILED = "Failed", _("Failed")

    mass_email = models.ForeignKey(
        MassEmail, on_delete=models.CASCADE, related_name="queue_items"
    )
    entity_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    entity_id = models.PositiveBigIntegerField(null=True, blank=True)
    entity = GenericForeignKey("entity_type", "entity_id")
    email_address = models.EmailField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    attempt_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.email_address} ({self.status})"


class LeadCapture(models.Model):
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    api_key = models.CharField(max_length=64, unique=True, blank=True, default="")
    campaign = models.ForeignKey(
        Campaign,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead_captures",
    )
    target_list = models.ForeignKey(
        TargetList,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead_captures",
    )
    source = models.CharField(max_length=30, blank=True, default="Web Site")
    default_assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    field_list = models.JSONField(
        default=list,
        blank=True,
        help_text='Allowed field names, e.g. ["first_name", "last_name", "email_address"].',
    )
    opt_in_confirmation = models.BooleanField(
        default=False, help_text="Require email confirmation before storing the lead."
    )
    opt_in_template = models.ForeignKey(
        EmailTemplate,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead_captures",
    )
    opt_in_lifetime_hours = models.PositiveIntegerField(default=48)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "lead captures"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = secrets.token_urlsafe(24)
        super().save(*args, **kwargs)
