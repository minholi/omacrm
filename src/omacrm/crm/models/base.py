from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from omacrm.core.models import BaseEntity


class Salutation(models.TextChoices):
    MR = "Mr.", _("Mr.")
    MS = "Ms.", _("Ms.")
    MRS = "Mrs.", _("Mrs.")
    DR = "Dr.", _("Dr.")


class Industry(models.TextChoices):
    ADVERTISING = "Advertising", _("Advertising")
    AEROSPACE = "Aerospace", _("Aerospace")
    AGRICULTURE = "Agriculture", _("Agriculture")
    APPAREL = "Apparel & Accessories", _("Apparel & Accessories")
    ARCHITECTURE = "Architecture", _("Architecture")
    AUTOMOTIVE = "Automotive", _("Automotive")
    BANKING = "Banking", _("Banking")
    BIOTECHNOLOGY = "Biotechnology", _("Biotechnology")
    BUILDING_MATERIALS = "Building Materials & Equipment", _("Building Materials & Equipment")
    CHEMICAL = "Chemical", _("Chemical")
    CONSTRUCTION = "Construction", _("Construction")
    CONSULTING = "Consulting", _("Consulting")
    COMPUTER = "Computer", _("Computer")
    CULTURE = "Culture", _("Culture")
    CREATIVE = "Creative", _("Creative")
    DEFENSE = "Defense", _("Defense")
    EDUCATION = "Education", _("Education")
    ELECTRONICS = "Electronics", _("Electronics")
    ELECTRIC_POWER = "Electric Power", _("Electric Power")
    ENERGY = "Energy", _("Energy")
    ENTERTAINMENT = "Entertainment & Leisure", _("Entertainment & Leisure")
    FINANCE = "Finance", _("Finance")
    FOOD_BEVERAGE = "Food & Beverage", _("Food & Beverage")
    GROCERY = "Grocery", _("Grocery")
    HEALTHCARE = "Healthcare", _("Healthcare")
    HOSPITALITY = "Hospitality", _("Hospitality")
    INSURANCE = "Insurance", _("Insurance")
    LEGAL = "Legal", _("Legal")
    MANUFACTURING = "Manufacturing", _("Manufacturing")
    MASS_MEDIA = "Mass Media", _("Mass Media")
    MARKETING = "Marketing", _("Marketing")
    MINING = "Mining", _("Mining")
    MUSIC = "Music", _("Music")
    PUBLISHING = "Publishing", _("Publishing")
    PETROLEUM = "Petroleum", _("Petroleum")
    REAL_ESTATE = "Real Estate", _("Real Estate")
    RETAIL = "Retail", _("Retail")
    SERVICE = "Service", _("Service")
    SPORTS = "Sports", _("Sports")
    SOFTWARE = "Software", _("Software")
    SUPPORT = "Support", _("Support")
    SHIPPING = "Shipping", _("Shipping")
    TRAVEL = "Travel", _("Travel")
    TECHNOLOGY = "Technology", _("Technology")
    TELECOMMUNICATIONS = "Telecommunications", _("Telecommunications")
    TELEVISION = "Television", _("Television")
    TRANSPORTATION = "Transportation", _("Transportation")
    TESTING = "Testing/Inspection/Certification", _("Testing/Inspection/Certification")
    VENTURE_CAPITAL = "Venture Capital", _("Venture Capital")
    WHOLESALE = "Wholesale", _("Wholesale")
    WATER = "Water", _("Water")


class LeadSource(models.TextChoices):
    CALL = "Call", _("Call")
    EMAIL = "Email", _("Email")
    EXISTING_CUSTOMER = "Existing Customer", _("Existing Customer")
    PARTNER = "Partner", _("Partner")
    PUBLIC_RELATIONS = "Public Relations", _("Public Relations")
    WEB_SITE = "Web Site", _("Web Site")
    CAMPAIGN = "Campaign", _("Campaign")
    OTHER = "Other", _("Other")


class AccountType(models.TextChoices):
    CUSTOMER = "Customer", _("Customer")
    INVESTOR = "Investor", _("Investor")
    PARTNER = "Partner", _("Partner")
    RESELLER = "Reseller", _("Reseller")


class OpportunityStage(models.TextChoices):
    PROSPECTING = "Prospecting", _("Prospecting")
    QUALIFICATION = "Qualification", _("Qualification")
    PROPOSAL = "Proposal", _("Proposal")
    NEGOTIATION = "Negotiation", _("Negotiation")
    CLOSED_WON = "Closed Won", _("Closed Won")
    CLOSED_LOST = "Closed Lost", _("Closed Lost")


OPPORTUNITY_PROBABILITY_MAP = {
    OpportunityStage.PROSPECTING: 10,
    OpportunityStage.QUALIFICATION: 20,
    OpportunityStage.PROPOSAL: 50,
    OpportunityStage.NEGOTIATION: 80,
    OpportunityStage.CLOSED_WON: 100,
    OpportunityStage.CLOSED_LOST: 0,
}
OPPORTUNITY_NON_CLOSED_STAGES = [
    OpportunityStage.PROSPECTING,
    OpportunityStage.QUALIFICATION,
    OpportunityStage.PROPOSAL,
    OpportunityStage.NEGOTIATION,
]


class ContactRole(models.TextChoices):
    DECISION_MAKER = "Decision Maker", _("Decision Maker")
    EVALUATOR = "Evaluator", _("Evaluator")
    INFLUENCER = "Influencer", _("Influencer")


class TaskStatus(models.TextChoices):
    NOT_STARTED = "Not Started", _("Not Started")
    STARTED = "Started", _("Started")
    COMPLETED = "Completed", _("Completed")
    CANCELED = "Canceled", _("Canceled")
    DEFERRED = "Deferred", _("Deferred")


class TaskPriority(models.TextChoices):
    LOW = "Low", _("Low")
    NORMAL = "Normal", _("Normal")
    HIGH = "High", _("High")
    URGENT = "Urgent", _("Urgent")


class EventStatus(models.TextChoices):
    PLANNED = "Planned", _("Planned")
    HELD = "Held", _("Held")
    NOT_HELD = "Not Held", _("Not Held")


class CallDirection(models.TextChoices):
    OUTBOUND = "Outbound", _("Outbound")
    INBOUND = "Inbound", _("Inbound")


class ReminderType(models.TextChoices):
    POPUP = "Popup", _("Popup")
    EMAIL = "Email", _("Email")


class BillingAddressMixin(models.Model):
    billing_address_street = models.CharField(max_length=255, blank=True, default="")
    billing_address_city = models.CharField(max_length=100, blank=True, default="")
    billing_address_state = models.CharField(max_length=100, blank=True, default="")
    billing_address_country = models.CharField(max_length=100, blank=True, default="")
    billing_address_postal_code = models.CharField(max_length=20, blank=True, default="")

    class Meta:
        abstract = True


class ShippingAddressMixin(models.Model):
    shipping_address_street = models.CharField(max_length=255, blank=True, default="")
    shipping_address_city = models.CharField(max_length=100, blank=True, default="")
    shipping_address_state = models.CharField(max_length=100, blank=True, default="")
    shipping_address_country = models.CharField(max_length=100, blank=True, default="")
    shipping_address_postal_code = models.CharField(max_length=20, blank=True, default="")

    class Meta:
        abstract = True


class AddressMixin(models.Model):
    address_street = models.CharField(max_length=255, blank=True, default="")
    address_city = models.CharField(max_length=100, blank=True, default="")
    address_state = models.CharField(max_length=100, blank=True, default="")
    address_country = models.CharField(max_length=100, blank=True, default="")
    address_postal_code = models.CharField(max_length=20, blank=True, default="")

    class Meta:
        abstract = True


class PersonNameMixin(models.Model):
    salutation = models.CharField(
        max_length=20, choices=Salutation.choices, blank=True, default=""
    )
    first_name = models.CharField(max_length=100, blank=True, default="")
    last_name = models.CharField(max_length=100, blank=True, default="")
    name = models.CharField(max_length=255, blank=True, default="", db_index=True)

    class Meta:
        abstract = True

    def build_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def save(self, *args, **kwargs):
        if not self.name:
            self.name = self.build_name()
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = list(kwargs["update_fields"]) + ["name"]
        super().save(*args, **kwargs)


class Event(BaseEntity):
    """Shared base for calendar events (Call/Meeting)."""

    name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=EventStatus.choices, default=EventStatus.PLANNED
    )
    date_start = models.DateTimeField(null=True, blank=True)
    date_end = models.DateTimeField(null=True, blank=True)
    duration = models.PositiveIntegerField(null=True, blank=True, help_text="Seconds")
    reminders = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True, default="")
    recurrence_rule = models.JSONField(default=dict, blank=True)
    recurrence_uid = models.CharField(
        max_length=36, blank=True, default="", db_index=True
    )

    parent_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    parent_id = models.PositiveBigIntegerField(null=True, blank=True)
    parent = GenericForeignKey("parent_type", "parent_id")
    account = models.ForeignKey(
        "crm.Account", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        abstract = True
        ordering = ["-date_start", "name"]

    def clean(self):
        super().clean()
        if self.recurrence_rule:
            from omacrm.crm.services.recurrence import validate_rule

            validate_rule(self.recurrence_rule)
