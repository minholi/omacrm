import json

from django.test import TestCase
from django.urls import reverse

from omacrm.core.models import Note, Team, User
from omacrm.core.metadata.registry import registry


class StreamTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("author", "author@example.com", "pw")
        self.entity = registry.get("Team")
        self.previous_stream = self.entity.stream
        self.entity.stream = True

    def tearDown(self):
        self.entity.stream = self.previous_stream

    def test_create_and_update_notes(self):
        team = Team.objects.create(name="Stream Team")
        self.assertTrue(
            Note.objects.filter(type=Note.Type.CREATE, parent_id=team.pk).exists()
        )

        team.description = "Updated description"
        team.save()
        note = Note.objects.filter(type=Note.Type.UPDATE, parent_id=team.pk).first()
        self.assertIsNotNone(note)
        self.assertIn("description", note.data)
        self.assertEqual(note.data["description"]["became"], "Updated description")


class ApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("apiadmin", "api@example.com", "pw")
        self.client.force_login(self.admin)

    def test_team_crud(self):
        response = self.client.post(
            "/api/v1/team/",
            data=json.dumps({"name": "API Team", "custom_data": {"region": "emea"}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        team_id = response.json()["id"]

        response = self.client.get("/api/v1/team/")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()["count"], 1)

        response = self.client.patch(
            f"/api/v1/team/{team_id}/",
            data=json.dumps({"description": "Updated"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)

        response = self.client.delete(f"/api/v1/team/{team_id}/")
        self.assertEqual(response.status_code, 204)

    def test_authentication_required(self):
        self.client.logout()
        response = self.client.get("/api/v1/team/")
        self.assertIn(response.status_code, (401, 403))


class AdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin2", "admin2@example.com", "pw")
        self.client.force_login(self.admin)

    def test_admin_pages_render(self):
        for name in (
            "admin:index",
            "admin:core_user_changelist",
            "admin:core_team_changelist",
            "admin:core_role_changelist",
            "admin:core_customfield_changelist",
            "admin:core_layout_changelist",
            "admin:core_job_changelist",
            "admin:core_scheduledjob_changelist",
            "admin:core_note_changelist",
            "admin:core_notification_changelist",
        ):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)

    def test_custom_field_roundtrip(self):
        from omacrm.core.models import CustomField

        CustomField.objects.create(
            entity_type="Team",
            name="region",
            field_type=CustomField.FieldType.ENUM,
            label="Region",
            params={"choices": [["emea", "EMEA"], ["amer", "AMER"]]},
        )
        data = {
            "name": "Custom Field Team",
            "description": "",
            "custom__region": "emea",
            "_save": "Save",
            "memberships-TOTAL_FORMS": "0",
            "memberships-INITIAL_FORMS": "0",
            "memberships-MIN_NUM_FORMS": "0",
            "memberships-MAX_NUM_FORMS": "1000",
        }
        response = self.client.post(reverse("admin:core_team_add"), data)
        self.assertEqual(response.status_code, 302, response.content)
        team = Team.objects.get(name="Custom Field Team")
        self.assertEqual(team.custom_data, {"region": "emea"})

        response = self.client.get(reverse("admin:core_team_change", args=[team.pk]))
        self.assertContains(response, 'value="emea" selected')
