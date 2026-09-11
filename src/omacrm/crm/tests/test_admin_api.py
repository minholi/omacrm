import json

from django.test import TestCase
from django.urls import reverse

from omacrm.core.models import User
from omacrm.crm.models import Account, Contact


class CrmAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("crm-admin", "crm@example.com", "pw")
        self.client.force_login(self.admin)

    def test_changelists_render(self):
        for name in (
            "admin:crm_account_changelist",
            "admin:crm_contact_changelist",
            "admin:crm_lead_changelist",
            "admin:crm_opportunity_changelist",
            "admin:crm_task_changelist",
            "admin:crm_call_changelist",
            "admin:crm_meeting_changelist",
        ):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)

    def test_duplicate_check_on_create(self):
        Account.objects.create(name="Duplicate Co", email_address="dup@example.com")
        data = {
            "name": "Duplicate Co",
            "email_address": "dup@example.com",
            "contact_links-TOTAL_FORMS": "0",
            "contact_links-INITIAL_FORMS": "0",
            "contact_links-MIN_NUM_FORMS": "0",
            "contact_links-MAX_NUM_FORMS": "1000",
            "_save": "Save",
        }
        response = self.client.post(reverse("admin:crm_account_add"), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Duplicate")
        self.assertEqual(Account.objects.filter(name="Duplicate Co").count(), 1)

    def test_kb_wysiwyg_and_import_export(self):
        response = self.client.get(reverse("admin:crm_knowledgebasearticle_add"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "trix")

        changelist = self.client.get(
            reverse("admin:crm_knowledgebasearticle_changelist")
        )
        self.assertContains(changelist, "Import")


class CrmApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("api-crm", "apicrm@example.com", "pw")
        self.client.force_login(self.admin)

    def test_account_crud_and_search(self):
        response = self.client.post(
            "/api/v1/account/",
            data=json.dumps(
                {"name": "API Account", "email_address": "api@account.com"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        account_id = response.json()["id"]

        response = self.client.get("/api/v1/account/?search=API")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()["count"], 1)

        response = self.client.patch(
            f"/api/v1/account/{account_id}/",
            data=json.dumps({"phone_number": "555"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_opportunity_money_field(self):
        response = self.client.post(
            "/api/v1/opportunity/",
            data=json.dumps(
                {
                    "name": "API Deal",
                    "amount": "1500.00",
                    "amount_currency": "USD",
                    "stage": "Proposal",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["probability"], 50)
