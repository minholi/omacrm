from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from omacrm.core.models import BaseEntity
from omacrm.crm.models.base import (
    CallDirection,
    Event,
    EventStatus,
    ReminderType,
    TaskPriority,
    TaskStatus,
)


class Task(BaseEntity):
    name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=TaskStatus.choices, default=TaskStatus.NOT_STARTED
    )
    priority = models.CharField(
        max_length=20, choices=TaskPriority.choices, default=TaskPriority.NORMAL
    )
    date_start = models.DateTimeField(null=True, blank=True)
    date_end = models.DateTimeField(null=True, blank=True)
    date_completed = models.DateTimeField(null=True, blank=True, editable=False)
    reminders = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True, default="")

    parent_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    parent_id = models.PositiveBigIntegerField(null=True, blank=True)
    parent = GenericForeignKey("parent_type", "parent_id")
    account = models.ForeignKey(
        "crm.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks",
    )
    contact = models.ForeignKey(
        "crm.Contact",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def is_overdue(self):
        if self.date_end and self.status not in {
            TaskStatus.COMPLETED,
            TaskStatus.CANCELED,
        }:
            return self.date_end < timezone.now()
        return False


class Call(Event):
    direction = models.CharField(
        max_length=20, choices=CallDirection.choices, default=CallDirection.OUTBOUND
    )
    uid = models.CharField(max_length=64, blank=True, default="")

    class Meta(Event.Meta):
        verbose_name = "Call"

    def __str__(self):
        return self.name


class Meeting(Event):
    is_all_day = models.BooleanField(default=False)
    join_url = models.URLField(blank=True, default="")
    external_service = models.CharField(max_length=50, blank=True, default="")

    class Meta(Event.Meta):
        verbose_name = "Meeting"

    def __str__(self):
        return self.name


class Reminder(models.Model):
    remind_at = models.DateTimeField(db_index=True)
    start_at = models.DateTimeField(null=True, blank=True)
    type = models.CharField(
        max_length=10, choices=ReminderType.choices, default=ReminderType.POPUP
    )
    seconds = models.PositiveIntegerField(default=0)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="reminders",
    )
    entity_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    entity_id = models.PositiveBigIntegerField(null=True, blank=True)
    entity = GenericForeignKey("entity_type", "entity_id")
    is_submitted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["remind_at"]

    def __str__(self):
        return f"Reminder #{self.pk} at {self.remind_at:%Y-%m-%d %H:%M}"


class AcceptanceStatus(models.TextChoices):
    NONE = "None", _("None")
    ACCEPTED = "Accepted", _("Accepted")
    TENTATIVE = "Tentative", _("Tentative")
    DECLINED = "Declined", _("Declined")


class Attendance(models.Model):
    """A user, contact or lead invited to a Call/Meeting."""

    event_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="+"
    )
    event_id = models.PositiveBigIntegerField()
    event = GenericForeignKey("event_type", "event_id", for_concrete_model=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attendances",
    )
    contact = models.ForeignKey(
        "crm.Contact",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attendances",
    )
    lead = models.ForeignKey(
        "crm.Lead",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attendances",
    )
    status = models.CharField(
        max_length=20,
        choices=AcceptanceStatus.choices,
        default=AcceptanceStatus.NONE,
    )
    invitation_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["pk"]
        verbose_name_plural = "attendances"

    def __str__(self):
        return str(self.display_name or f"Attendance #{self.pk}")

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError

        selected = [bool(self.user_id), bool(self.contact_id), bool(self.lead_id)]
        if sum(selected) != 1:
            raise ValidationError(
                "Select exactly one attendee: user, contact or lead."
            )

    @property
    def display_name(self):
        target = self.user or self.contact or self.lead
        return target.name if target is not None and hasattr(target, "name") else str(target or "")

    @property
    def email(self) -> str:
        target = self.user or self.contact or self.lead
        if target is None:
            return ""
        return (
            getattr(target, "email", "")
            or getattr(target, "email_address", "")
            or ""
        )
