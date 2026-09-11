from urllib.parse import parse_qs, urlparse

from django.test import TestCase
from django.urls import reverse

from omacrm.core.models import SavedFilter, User
from omacrm.crm.models import Task


class SavedFilterTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("saved", "saved@example.com", "pw")
        self.client.force_login(self.admin)
        self.url = reverse("admin:crm_task_changelist")

    def test_save_creates_filter_and_redirects(self):
        response = self.client.get(
            self.url, {"status": "Completed", "save_filter": "Done tasks"}
        )
        self.assertEqual(response.status_code, 302)
        saved = SavedFilter.objects.get(user=self.admin, entity_type="Task")
        self.assertEqual(saved.name, "Done tasks")
        self.assertEqual(saved.params.get("status"), "Completed")
        self.assertNotIn("save_filter", response["Location"])
        self.assertIn("status=Completed", response["Location"])

    def test_changelist_renders_saved_filters(self):
        SavedFilter.objects.create(
            user=self.admin,
            entity_type="Task",
            name="My completed tasks",
            params={"status": "Completed"},
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My completed tasks")
        self.assertContains(response, "apply_filter=")

    def test_apply_redirects_with_params(self):
        saved = SavedFilter.objects.create(
            user=self.admin,
            entity_type="Task",
            name="Mine",
            params={"status": "Completed"},
        )
        response = self.client.get(self.url, {"apply_filter": saved.pk})
        self.assertEqual(response.status_code, 302)
        query = parse_qs(urlparse(response["Location"]).query)
        self.assertEqual(query.get("status"), ["Completed"])

    def test_delete_removes_filter(self):
        saved = SavedFilter.objects.create(
            user=self.admin, entity_type="Task", name="Temp", params={}
        )
        response = self.client.get(self.url, {"delete_filter": saved.pk})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SavedFilter.objects.filter(pk=saved.pk).exists())

    def test_filters_are_user_scoped(self):
        other = User.objects.create_user("other-saved", "other@example.com", "pw")
        saved = SavedFilter.objects.create(
            user=other,
            entity_type="Task",
            name="Theirs",
            params={"status": "Completed"},
        )

        response = self.client.get(self.url, {"apply_filter": saved.pk})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("status=Completed", response["Location"])

        self.client.get(self.url, {"delete_filter": saved.pk})
        self.assertTrue(SavedFilter.objects.filter(pk=saved.pk).exists())
