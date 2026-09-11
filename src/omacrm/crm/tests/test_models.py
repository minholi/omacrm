from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from omacrm.crm.models import Account, Call, Contact, Lead, Opportunity, Task


class OpportunityRulesTests(TestCase):
    def test_probability_and_last_stage_on_create(self):
        opportunity = Opportunity.objects.create(
            name="Deal", stage="Qualification", amount=Money(1000, "USD")
        )
        opportunity.refresh_from_db()
        self.assertEqual(opportunity.probability, 20)
        self.assertEqual(opportunity.last_stage, "Qualification")
        self.assertEqual(opportunity.amount_weighted, Decimal("200.00"))

    def test_stage_change_updates_probability_and_keeps_last_stage(self):
        opportunity = Opportunity.objects.create(
            name="Deal", stage="Prospecting", amount=Money(1000, "USD")
        )
        opportunity.stage = "Negotiation"
        opportunity.save()
        opportunity.refresh_from_db()
        self.assertEqual(opportunity.probability, 80)
        self.assertEqual(opportunity.last_stage, "Negotiation")

        opportunity.stage = "Closed Won"
        opportunity.save()
        opportunity.refresh_from_db()
        self.assertEqual(opportunity.probability, 100)
        self.assertEqual(opportunity.last_stage, "Negotiation")
        self.assertEqual(opportunity.amount_weighted, Decimal("1000.00"))

    def test_explicit_probability_is_preserved(self):
        opportunity = Opportunity.objects.create(
            name="Deal", stage="Prospecting", probability=42
        )
        opportunity.stage = "Proposal"
        opportunity.save()
        opportunity.refresh_from_db()
        self.assertEqual(opportunity.probability, 42)
        self.assertEqual(opportunity.last_stage, "Proposal")


class MiscRulesTests(TestCase):
    def test_person_name_built(self):
        contact = Contact.objects.create(first_name="John", last_name="Doe")
        self.assertEqual(contact.name, "John Doe")

    def test_task_date_completed(self):
        task = Task.objects.create(name="Task", status="Completed")
        self.assertIsNotNone(task.date_completed)

        task.status = "Started"
        task.save()
        task.refresh_from_db()
        self.assertIsNone(task.date_completed)

    def test_lead_converted_at(self):
        lead = Lead.objects.create(
            first_name="Jane", last_name="Doe", status=Lead.Status.CONVERTED
        )
        self.assertIsNotNone(lead.converted_at)

    def test_contact_primary_account_link(self):
        account = Account.objects.create(name="Acme")
        contact = Contact.objects.create(
            first_name="John", last_name="Doe", account=account
        )
        self.assertTrue(
            account.contact_links.filter(contact=contact).exists()
        )

    def test_event_duration(self):
        from datetime import timedelta

        from django.utils import timezone

        start = timezone.now()
        call = Call.objects.create(
            name="Call", date_start=start, date_end=start + timedelta(minutes=30)
        )
        self.assertEqual(call.duration, 1800)
