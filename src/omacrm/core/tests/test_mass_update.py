from django.test import TestCase
from django.urls import reverse

from omacrm.core.models import User
from omacrm.crm.models import Task


class MassUpdateTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("mass", "mass@example.com", "pw")
        self.client.force_login(self.admin)
        self.task1 = Task.objects.create(name="One", status="Not Started")
        self.task2 = Task.objects.create(name="Two", status="Not Started")

    def _start(self):
        response = self.client.post(
            reverse("admin:crm_task_changelist"),
            {
                "action": "mass_update",
                "_selected_action": [self.task1.pk, self.task2.pk],
                "index": "0",
                "select_across": "0",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("mass-update", response["Location"])
        return response["Location"]

    def test_action_redirects_to_form_with_selection(self):
        location = self._start()
        response = self.client.get(location)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2 records selected")
        self.assertContains(response, "Set field")

    def test_apply_enum_value(self):
        location = self._start()
        token = location.split("token=", 1)[1]
        response = self.client.post(
            reverse("admin:crm_task_mass_update"),
            {"token": token, "definition": "status:Completed"},
        )
        self.assertEqual(response.status_code, 302)
        self.task1.refresh_from_db()
        self.task2.refresh_from_db()
        self.assertEqual(self.task1.status, "Completed")
        self.assertEqual(self.task2.status, "Completed")
        self.assertIsNotNone(self.task1.date_completed)

    def test_apply_assigned_user(self):
        location = self._start()
        token = location.split("token=", 1)[1]
        self.client.post(
            reverse("admin:crm_task_mass_update"),
            {"token": token, "definition": f"assigned_user:{self.admin.pk}"},
        )
        self.task1.refresh_from_db()
        self.assertEqual(self.task1.assigned_user, self.admin)

    def test_invalid_value_is_rejected(self):
        location = self._start()
        token = location.split("token=", 1)[1]
        response = self.client.post(
            reverse("admin:crm_task_mass_update"),
            {"token": token, "definition": "status:Does Not Exist"},
            follow=True,
        )
        self.task1.refresh_from_db()
        self.assertEqual(self.task1.status, "Not Started")
        self.assertContains(response, "Invalid mass update value")

    def test_expired_selection_is_rejected(self):
        response = self.client.post(
            reverse("admin:crm_task_mass_update"),
            {"token": "missing", "definition": "status:Completed"},
            follow=True,
        )
        self.assertContains(response, "selection expired")
