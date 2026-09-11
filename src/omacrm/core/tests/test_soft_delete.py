from django.test import TestCase
from django.urls import reverse

from omacrm.core.models import User
from omacrm.crm.models import Account


class SoftDeleteAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("soft", "soft@example.com", "pw")
        self.client.force_login(self.admin)
        self.url = reverse("admin:crm_account_changelist")
        self.active = Account.objects.create(name="Active Account")
        self.deleted = Account.objects.create(name="Deleted Account")
        self.deleted.delete()

    def test_default_changelist_hides_deleted(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Active Account")
        self.assertNotContains(response, "Deleted Account")
        self.assertContains(response, "Show deleted records")

    def test_deleted_mode_lists_only_deleted(self):
        response = self.client.get(self.url, {"deleted": "1"})
        self.assertContains(response, "Deleted Account")
        self.assertNotContains(response, "Active Account")
        self.assertContains(response, "Show active records")

    def test_row_action_restores_record(self):
        response = self.client.post(
            f"/admin/crm/account/{self.deleted.pk}/restore_record/"
        )
        self.assertEqual(response.status_code, 302)
        self.deleted.refresh_from_db()
        self.assertFalse(self.deleted.deleted)

    def test_bulk_action_restores_selection(self):
        response = self.client.post(
            f"{self.url}?deleted=1",
            {
                "action": "restore_selected",
                "_selected_action": [self.deleted.pk],
                "index": "0",
                "select_across": "0",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.deleted.refresh_from_db()
        self.assertFalse(self.deleted.deleted)

    def test_restore_action_on_active_record_is_noop(self):
        response = self.client.post(
            f"/admin/crm/account/{self.active.pk}/restore_record/", follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.active.refresh_from_db()
        self.assertFalse(self.active.deleted)

    def test_api_excludes_soft_deleted(self):
        response = self.client.get("/api/v1/account/")
        self.assertEqual(response.status_code, 200)
        names = [item["name"] for item in response.json()["results"]]
        self.assertIn("Active Account", names)
        self.assertNotIn("Deleted Account", names)
