from django.contrib.contenttypes.models import ContentType

from omacrm.core.services.duplicates import check_duplicates
from omacrm.crm.models import Account, AccountContact, Call, Contact, Lead, Meeting, Opportunity, Task

CONVERT_MODEL_FIELDS = {
    "Account": [
        "name",
        "website",
        "email_address",
        "phone_number",
        "type",
        "industry",
        "sic_code",
        "billing_address_street",
        "billing_address_city",
        "billing_address_state",
        "billing_address_country",
        "billing_address_postal_code",
    ],
    "Contact": [
        "salutation",
        "first_name",
        "last_name",
        "title",
        "email_address",
        "phone_number",
        "address_street",
        "address_city",
        "address_state",
        "address_country",
        "address_postal_code",
    ],
    "Opportunity": [
        "name",
        "amount",
        "lead_source",
        "close_date",
    ],
}

CONVERT_MODELS = {
    "Account": Account,
    "Contact": Contact,
    "Opportunity": Opportunity,
}


class LeadConversionService:
    """Converts a Lead into Account / Contact / Opportunity records."""

    def __init__(self, user=None, skip_duplicate_check: bool = False):
        self.user = user
        self.skip_duplicate_check = skip_duplicate_check

    def get_convert_data(self, lead: Lead) -> dict:
        return {
            "Account": {
                "name": lead.account_name or lead.name or lead.email_address,
                "website": lead.website,
                "email_address": lead.email_address,
                "phone_number": lead.phone_number,
                "industry": lead.industry,
                "billing_address_street": lead.address_street,
                "billing_address_city": lead.address_city,
                "billing_address_state": lead.address_state,
                "billing_address_country": lead.address_country,
                "billing_address_postal_code": lead.address_postal_code,
            },
            "Contact": {
                "salutation": lead.salutation,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "title": lead.title,
                "email_address": lead.email_address,
                "phone_number": lead.phone_number,
                "address_street": lead.address_street,
                "address_city": lead.address_city,
                "address_state": lead.address_state,
                "address_country": lead.address_country,
                "address_postal_code": lead.address_postal_code,
            },
            "Opportunity": {
                "name": lead.name or lead.account_name,
                "amount": lead.opportunity_amount,
                "lead_source": lead.source,
            },
        }

    def _build(self, entity_name: str, values: dict):
        model = CONVERT_MODELS[entity_name]
        allowed = CONVERT_MODEL_FIELDS[entity_name]
        data = {key: value for key, value in (values or {}).items() if key in allowed}
        instance = model(**data)
        if self.user is not None:
            instance.created_by = self.user
            instance.modified_by = self.user
        if hasattr(instance, "assigned_user_id") and self.user is not None:
            instance.assigned_user = self.user
        return instance

    def convert(self, lead: Lead, data: dict) -> dict:
        created = {}

        account = None
        account_values = data.get("Account") or {}
        if account_values:
            account = self._build("Account", account_values)
            if not self.skip_duplicate_check:
                check_duplicates("Account", account)
            account.save()
            created["Account"] = account

        contact = None
        contact_values = data.get("Contact") or {}
        if contact_values:
            contact = self._build("Contact", contact_values)
            if account is not None:
                contact.account = account
            if not self.skip_duplicate_check:
                check_duplicates("Contact", contact)
            contact.save()
            if account is not None:
                AccountContact.objects.get_or_create(
                    account=account,
                    contact=contact,
                    defaults={"role": contact.title},
                )
            created["Contact"] = contact

        opportunity = None
        opportunity_values = data.get("Opportunity") or {}
        if opportunity_values:
            opportunity = self._build("Opportunity", opportunity_values)
            if account is not None:
                opportunity.account = account
            if contact is not None:
                opportunity.contact = contact
            if not self.skip_duplicate_check:
                check_duplicates("Opportunity", opportunity)
            opportunity.save()
            created["Opportunity"] = opportunity

        lead.created_account = account or lead.created_account
        lead.created_contact = contact or lead.created_contact
        lead.created_opportunity = opportunity or lead.created_opportunity
        lead.status = Lead.Status.CONVERTED
        if self.user is not None:
            lead.modified_by = self.user
        lead.save()

        self._reparent_activities(lead, opportunity or account)
        return created

    @staticmethod
    def _reparent_activities(lead: Lead, target) -> None:
        if target is None:
            return
        lead_ct = ContentType.objects.get_for_model(Lead)
        target_ct = ContentType.objects.get_for_model(target)
        for model in (Task, Call, Meeting):
            model.all_objects.filter(parent_type=lead_ct, parent_id=lead.pk).update(
                parent_type=target_ct, parent_id=target.pk
            )
