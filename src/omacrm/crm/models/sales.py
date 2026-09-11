from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField

from omacrm.core.models import BaseEntity
from omacrm.crm.models.base import (
    AccountType,
    AddressMixin,
    BillingAddressMixin,
    ContactRole,
    Industry,
    LeadSource,
    OpportunityStage,
    PersonNameMixin,
    ShippingAddressMixin,
)


class Account(BillingAddressMixin, ShippingAddressMixin, BaseEntity):
    name = models.CharField(max_length=255, db_index=True)
    website = models.URLField(blank=True, default="")
    email_address = models.EmailField(blank=True, default="")
    phone_number = models.CharField(max_length=50, blank=True, default="")
    type = models.CharField(
        max_length=20, choices=AccountType.choices, blank=True, default=""
    )
    industry = models.CharField(
        max_length=100, choices=Industry.choices, blank=True, default=""
    )
    sic_code = models.CharField(max_length=50, blank=True, default="")
    description = models.TextField(blank=True, default="")
    is_locked = models.BooleanField(default=False)

    contacts = models.ManyToManyField(
        "crm.Contact",
        through="crm.AccountContact",
        through_fields=("account", "contact"),
        related_name="accounts",
        blank=True,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Contact(PersonNameMixin, AddressMixin, BaseEntity):
    title = models.CharField(max_length=100, blank=True, default="")
    account = models.ForeignKey(
        Account,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="primary_contacts",
    )
    email_address = models.EmailField(blank=True, default="")
    phone_number = models.CharField(max_length=50, blank=True, default="")
    do_not_call = models.BooleanField(default=False)
    description = models.TextField(blank=True, default="")
    portal_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="portal_contact",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AccountContact(models.Model):
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="contact_links"
    )
    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, related_name="account_links"
    )
    role = models.CharField(max_length=100, blank=True, default="")
    is_inactive = models.BooleanField(default=False)

    class Meta:
        unique_together = [("account", "contact")]
        ordering = ["account__name", "contact__name"]

    def __str__(self):
        return f"{self.contact} @ {self.account}"


class Lead(PersonNameMixin, AddressMixin, BaseEntity):
    class Status(models.TextChoices):
        NEW = "New", _("New")
        ASSIGNED = "Assigned", _("Assigned")
        IN_PROCESS = "In Process", _("In Process")
        CONVERTED = "Converted", _("Converted")
        RECYCLED = "Recycled", _("Recycled")
        DEAD = "Dead", _("Dead")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    title = models.CharField(max_length=100, blank=True, default="")
    source = models.CharField(
        max_length=30, choices=LeadSource.choices, blank=True, default=""
    )
    industry = models.CharField(
        max_length=100, choices=Industry.choices, blank=True, default=""
    )
    opportunity_amount = MoneyField(
        max_digits=16,
        decimal_places=2,
        default_currency="USD",
        null=True,
        blank=True,
    )
    opportunity_amount_converted = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True, editable=False
    )
    website = models.URLField(blank=True, default="")
    email_address = models.EmailField(blank=True, default="")
    phone_number = models.CharField(max_length=50, blank=True, default="")
    do_not_call = models.BooleanField(default=False)
    description = models.TextField(blank=True, default="")
    account_name = models.CharField(max_length=255, blank=True, default="")
    converted_at = models.DateTimeField(null=True, blank=True, editable=False)
    opt_in_confirmed = models.BooleanField(default=False)
    opt_in_confirmed_at = models.DateTimeField(null=True, blank=True, editable=False)

    created_account = models.ForeignKey(
        Account,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="original_leads",
    )
    created_contact = models.ForeignKey(
        Contact,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="original_leads",
    )
    created_opportunity = models.ForeignKey(
        "crm.Opportunity",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="original_leads",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name or self.account_name or self.email_address or f"Lead #{self.pk}"


class Opportunity(BaseEntity):
    name = models.CharField(max_length=255, db_index=True)
    amount = MoneyField(
        max_digits=16,
        decimal_places=2,
        default_currency="USD",
        null=True,
        blank=True,
    )
    amount_weighted = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True, editable=False
    )
    amount_converted = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True, editable=False
    )
    stage = models.CharField(
        max_length=30,
        choices=OpportunityStage.choices,
        default=OpportunityStage.PROSPECTING,
    )
    last_stage = models.CharField(
        max_length=30, choices=OpportunityStage.choices, blank=True, default=""
    )
    probability = models.PositiveSmallIntegerField(null=True, blank=True)
    lead_source = models.CharField(
        max_length=30, choices=LeadSource.choices, blank=True, default=""
    )
    close_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True, default="")
    campaign = models.ForeignKey(
        "crm.Campaign",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="opportunities",
    )
    account = models.ForeignKey(
        Account,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="opportunities",
    )
    contact = models.ForeignKey(
        Contact,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="opportunities_primary",
    )
    contacts = models.ManyToManyField(
        Contact,
        through="crm.OpportunityContact",
        through_fields=("opportunity", "contact"),
        related_name="opportunities",
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class OpportunityContact(models.Model):
    opportunity = models.ForeignKey(
        Opportunity, on_delete=models.CASCADE, related_name="contact_links"
    )
    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, related_name="opportunity_links"
    )
    role = models.CharField(
        max_length=30, choices=ContactRole.choices, blank=True, default=""
    )

    class Meta:
        unique_together = [("opportunity", "contact")]
        ordering = ["opportunity__name", "contact__name"]

    def __str__(self):
        return f"{self.contact} @ {self.opportunity}"
