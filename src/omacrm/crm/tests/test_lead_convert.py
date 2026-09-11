from djmoney.money import Money
from django.test import TestCase

from omacrm.core.models import User
from omacrm.crm.models import Account, Contact, Lead, Opportunity, Task
from omacrm.crm.services import LeadConversionService


class LeadConversionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("conv", "conv@example.com", "pw")
        self.lead = Lead.objects.create(
            salutation="Mr.",
            first_name="Jane",
            last_name="Doe",
            account_name="Doe Industries",
            email_address="jane@doe.com",
            phone_number="555-0100",
            opportunity_amount=Money(2500, "USD"),
            source="Web Site",
            address_city="Springfield",
        )
        self.service = LeadConversionService(self.user)

    def test_get_convert_data(self):
        data = self.service.get_convert_data(self.lead)
        self.assertEqual(data["Account"]["name"], "Doe Industries")
        self.assertEqual(data["Contact"]["last_name"], "Doe")
        self.assertEqual(data["Opportunity"]["lead_source"], "Web Site")
        self.assertEqual(data["Opportunity"]["amount"].amount, 2500)

    def test_convert_creates_and_links_records(self):
        data = self.service.get_convert_data(self.lead)
        created = self.service.convert(self.lead, data)

        self.assertIn("Account", created)
        self.assertIn("Contact", created)
        self.assertIn("Opportunity", created)

        contact = created["Contact"]
        opportunity = created["Opportunity"]
        self.assertEqual(contact.account_id, created["Account"].pk)
        self.assertTrue(
            created["Account"].contact_links.filter(contact=contact).exists()
        )
        self.assertEqual(opportunity.account_id, created["Account"].pk)
        self.assertEqual(opportunity.contact_id, contact.pk)

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, Lead.Status.CONVERTED)
        self.assertIsNotNone(self.lead.converted_at)
        self.assertEqual(self.lead.created_account_id, created["Account"].pk)
        self.assertEqual(self.lead.created_contact_id, contact.pk)
        self.assertEqual(self.lead.created_opportunity_id, opportunity.pk)

    def test_convert_reparents_activities(self):
        task = Task.objects.create(name="Follow up", parent=self.lead)
        data = self.service.get_convert_data(self.lead)
        created = self.service.convert(self.lead, data)
        task.refresh_from_db()
        self.assertEqual(task.parent_id, created["Opportunity"].pk)

    def test_convert_skips_empty_sections(self):
        created = self.service.convert(self.lead, {"Account": {"name": "Only Co"}})
        self.assertIn("Account", created)
        self.assertNotIn("Contact", created)
        self.assertNotIn("Opportunity", created)


class LeadConvertAdminActionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "convert-admin", "ca@example.com", "pw"
        )
        self.client.force_login(self.admin)
        self.lead = Lead.objects.create(
            first_name="Ann", last_name="Smith", account_name="Smith Co"
        )

    def test_convert_action(self):
        url = f"/admin/crm/lead/{self.lead.pk}/convert_lead/"
        response = self.client.post(
            url,
            {
                "_form_submitted": "on",
                "create_account": "on",
                "create_contact": "on",
                "create_opportunity": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("/admin/crm/opportunity/", response.headers.get("HX-Redirect", ""))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, Lead.Status.CONVERTED)
