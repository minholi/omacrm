from django.db import models
from django.utils.translation import gettext_lazy as _

from omacrm.core.models import BaseEntity
from omacrm.crm.models.sales import Account, Contact, Lead


class Case(BaseEntity):
    class Status(models.TextChoices):
        NEW = "New", _("New")
        ASSIGNED = "Assigned", _("Assigned")
        PENDING = "Pending", _("Pending")
        CLOSED = "Closed", _("Closed")
        REJECTED = "Rejected", _("Rejected")
        DUPLICATE = "Duplicate", _("Duplicate")

    class Priority(models.TextChoices):
        LOW = "Low", _("Low")
        NORMAL = "Normal", _("Normal")
        HIGH = "High", _("High")
        URGENT = "Urgent", _("Urgent")

    class Type(models.TextChoices):
        QUESTION = "Question", _("Question")
        INCIDENT = "Incident", _("Incident")
        PROBLEM = "Problem", _("Problem")

    name = models.CharField(max_length=255, db_index=True)
    number = models.PositiveIntegerField(
        null=True, blank=True, unique=True, editable=False
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    priority = models.CharField(
        max_length=20, choices=Priority.choices, default=Priority.NORMAL
    )
    type = models.CharField(max_length=20, choices=Type.choices, blank=True, default="")
    description = models.TextField(blank=True, default="")
    account = models.ForeignKey(
        Account,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cases",
    )
    contact = models.ForeignKey(
        Contact,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cases",
    )
    lead = models.ForeignKey(
        Lead,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cases",
    )
    is_internal = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Case"
        verbose_name_plural = "Cases"

    def __str__(self):
        return f"#{self.number} {self.name}" if self.number else self.name

    @property
    def is_open(self):
        return self.status not in {self.Status.CLOSED, self.Status.REJECTED}
