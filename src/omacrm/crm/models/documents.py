from django.db import models
from django.utils.translation import gettext_lazy as _

from omacrm.core.models import BaseEntity, CustomDataMixin
from omacrm.crm.models.sales import Account, Contact, Lead, Opportunity


class DocumentFolder(CustomDataMixin, models.Model):
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

    def __str__(self):
        return self.name


class Document(BaseEntity):
    class Status(models.TextChoices):
        DRAFT = "Draft", _("Draft")
        ACTIVE = "Active", _("Active")
        CANCELED = "Canceled", _("Canceled")
        EXPIRED = "Expired", _("Expired")

    class Type(models.TextChoices):
        CONTRACT = "Contract", _("Contract")
        NDA = "NDA", _("NDA")
        EULA = "EULA", _("EULA")
        LICENSE_AGREEMENT = "License Agreement", _("License Agreement")

    name = models.CharField(max_length=255, db_index=True)
    file = models.FileField(upload_to="documents/%Y/%m/", blank=True, default="")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    type = models.CharField(max_length=30, choices=Type.choices, blank=True, default="")
    publish_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True, default="")
    folder = models.ForeignKey(
        DocumentFolder,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documents",
    )
    accounts = models.ManyToManyField(Account, blank=True, related_name="documents")
    contacts = models.ManyToManyField(Contact, blank=True, related_name="documents")
    leads = models.ManyToManyField(Lead, blank=True, related_name="documents")
    opportunities = models.ManyToManyField(
        Opportunity, blank=True, related_name="documents"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
