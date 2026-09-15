import json

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from omacrm.core.models import Layout, User


class EditorMetadataTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser(
            "editor-admin", "editor@example.com", "pw"
        )
        self.client.force_login(self.staff)
        self.url = reverse("editor_metadata", kwargs={"entity_type": "Task"})

    def test_requires_staff(self):
        user = User.objects.create_user(
            "editor-user", "editor-user@example.com", "pw"
        )
        client = self.client_class()
        client.force_login(user)
        self.assertEqual(client.get(self.url).status_code, 302)

    def test_requires_authentication(self):
        client = self.client_class()
        response = client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_unknown_entity_returns_404(self):
        url = reverse("editor_metadata", kwargs={"entity_type": "Nope"})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_payload_describes_fields_actions_and_operators(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["entityType"], "Task")

        fields = {field["name"]: field for field in payload["fields"]}
        self.assertIn("status", fields)
        self.assertEqual(fields["status"]["type"], "enum")
        self.assertTrue(fields["status"]["choices"])
        self.assertIn("name", fields)

        self.assertIn("wait", payload["actions"])
        self.assertIn("branch", payload["actions"])
        self.assertIn("equals", payload["operators"])
        self.assertIn("notify", payload["formulaHelpers"])
        self.assertTrue(payload["entityTypes"])

    def test_metadata_rejects_post(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)


class EditorValidateTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser(
            "editor-validate", "editor-validate@example.com", "pw"
        )
        self.client.force_login(self.staff)
        self.url = reverse("editor_validate")

    def _post(self, kind, value, entity_type="Task"):
        return self.client.post(
            self.url,
            data=json.dumps(
                {"kind": kind, "entity_type": entity_type, "value": value}
            ),
            content_type="application/json",
        )

    def test_requires_staff(self):
        user = User.objects.create_user(
            "editor-validate-user", "editor-validate-user@example.com", "pw"
        )
        client = self.client_class()
        client.force_login(user)
        response = client.post(
            self.url, data="{}", content_type="application/json"
        )
        self.assertEqual(response.status_code, 302)

    def test_workflow_actions_valid(self):
        response = self._post(
            "workflow_actions",
            [
                {"type": "wait", "duration": "3d"},
                {"type": "notify", "message": "Hi"},
            ],
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "errors": []})

    def test_workflow_actions_collects_all_errors(self):
        response = self._post(
            "workflow_actions",
            [
                {"type": "set_field", "field": "nope", "value": 1},
                {"type": "notify", "message": "x"},
                {"type": "wait", "duration": "soon"},
            ],
        )
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(len(payload["errors"]), 2)
        self.assertEqual(payload["errors"][0]["path"], "Action #1")
        self.assertIn("unknown field", payload["errors"][0]["message"])
        self.assertIn("invalid duration", payload["errors"][1]["message"])

    def test_workflow_actions_nested_error_path(self):
        response = self._post(
            "workflow_actions",
            [
                {
                    "type": "branch",
                    "condition": "status == 'Started'",
                    "then": [{"type": "set_field", "field": "nope", "value": 1}],
                }
            ],
        )
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["errors"][0]["path"], "Action #1 (then) Action #1")

    def test_workflow_actions_require_entity_type(self):
        response = self._post("workflow_actions", [], entity_type="")
        self.assertTrue(response.json()["ok"])
        response = self._post(
            "workflow_actions", [{"type": "notify"}], entity_type=""
        )
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["errors"][0]["path"], "entity_type")

    def test_dynamic_logic_valid_and_invalid(self):
        valid = self._post(
            "dynamic_logic",
            {"type": "equals", "attribute": "status", "value": "Started"},
        )
        self.assertTrue(valid.json()["ok"])

        invalid = self._post("dynamic_logic", {"type": "nope"})
        payload = invalid.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["errors"][0]["path"], "condition")

    def test_formula_valid_and_invalid(self):
        valid = self._post("formula", "priority = 'High'")
        self.assertTrue(valid.json()["ok"])

        invalid = self._post("formula", "priority = (")
        payload = invalid.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["errors"][0]["path"], "script")

    def test_custom_field_valid_and_invalid(self):
        valid = self._post(
            "custom_field",
            {"name": "code", "field_type": "varchar", "params": {}},
        )
        self.assertTrue(valid.json()["ok"])

        invalid = self._post(
            "custom_field",
            {"name": "Bad Name", "field_type": "varchar", "params": {}},
        )
        payload = invalid.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["errors"][0]["path"], "name")

    def test_lead_capture_valid_and_invalid(self):
        valid = self._post(
            "lead_capture", ["first_name", "email_address"], entity_type=""
        )
        self.assertTrue(valid.json()["ok"])

        invalid = self._post("lead_capture", ["nope"], entity_type="")
        payload = invalid.json()
        self.assertFalse(payload["ok"])
        self.assertIn("Unknown Lead field", payload["errors"][0]["message"])

    def test_layout_valid_and_invalid(self):
        response = self.client.post(
            self.url,
            data=json.dumps(
                {
                    "kind": "layout",
                    "entity_type": "Task",
                    "layout_name": "list",
                    "value": ["name", "status"],
                }
            ),
            content_type="application/json",
        )
        self.assertTrue(response.json()["ok"])

        response = self.client.post(
            self.url,
            data=json.dumps(
                {
                    "kind": "layout",
                    "entity_type": "Task",
                    "layout_name": "list",
                    "value": ["name", "nope"],
                }
            ),
            content_type="application/json",
        )
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertIn("Unknown field: nope", payload["errors"][0]["message"])

    def test_layout_detail_sections(self):
        response = self.client.post(
            self.url,
            data=json.dumps(
                {
                    "kind": "layout",
                    "entity_type": "Task",
                    "layout_name": "detail",
                    "value": [{"title": "Overview", "fields": ["name"]}],
                }
            ),
            content_type="application/json",
        )
        self.assertTrue(response.json()["ok"])

        response = self.client.post(
            self.url,
            data=json.dumps(
                {
                    "kind": "layout",
                    "entity_type": "Task",
                    "layout_name": "detail",
                    "value": [{"title": "Overview", "fields": ["nope"]}],
                }
            ),
            content_type="application/json",
        )
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["errors"][0]["path"], "data[0].fields")

    def test_layout_requires_layout_name(self):
        response = self.client.post(
            self.url,
            data=json.dumps(
                {
                    "kind": "layout",
                    "entity_type": "Task",
                    "value": [],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.json()["errors"][0]["path"], "layout_name")

    def test_reminders_valid_and_invalid(self):
        valid = self._post(
            "reminders",
            [{"type": "Popup", "seconds": 3600}],
            entity_type="",
        )
        self.assertTrue(valid.json()["ok"])

        invalid = self._post(
            "reminders",
            [{"type": "Nope", "seconds": -1}],
            entity_type="",
        )
        payload = invalid.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(len(payload["errors"]), 2)
        self.assertEqual(payload["errors"][0]["path"], "reminders[0]")

    def test_recurrence_valid_and_invalid(self):
        valid = self._post(
            "recurrence",
            {"frequency": "weekly", "interval": 1, "weekdays": [0, 2]},
            entity_type="",
        )
        self.assertTrue(valid.json()["ok"])

        invalid = self._post(
            "recurrence",
            {"frequency": "yearly"},
            entity_type="",
        )
        payload = invalid.json()
        self.assertFalse(payload["ok"])
        self.assertIn("frequency", payload["errors"][0]["message"])

    def test_recurrence_empty_is_allowed(self):
        response = self._post("recurrence", {}, entity_type="")
        self.assertTrue(response.json()["ok"])

    def test_unknown_kind_returns_400(self):
        response = self._post("nope", {})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_invalid_json_returns_400(self):
        response = self.client.post(
            self.url, data="{not json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_validate_rejects_get(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)


class EditorAdminTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser(
            "editor-forms", "editor-forms@example.com", "pw"
        )
        self.client.force_login(self.staff)

    def _assert_editor(self, url_name, kind, visual=True):
        response = self.client.get(reverse(url_name))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "vendor/codemirror/codemirror6.bundle.js")
        self.assertContains(response, "core/js/editors.js")
        self.assertContains(response, "core/js/builders.js")
        self.assertContains(response, "data-editor-root")
        self.assertContains(response, '"kind": "%s"' % kind)
        self.assertContains(response, '"classes"')
        if visual:
            self.assertContains(response, "data-editor-tabs")
            self.assertContains(response, "data-editor-visual")
            self.assertContains(response, '"tabs": true')
        else:
            self.assertContains(response, '"tabs": false')
            self.assertNotContains(response, "data-editor-tabs")

    def test_editor_assets_exist(self):
        self.assertIsNotNone(
            finders.find("vendor/codemirror/codemirror6.bundle.js")
        )
        self.assertIsNotNone(finders.find("core/js/editors.js"))
        self.assertIsNotNone(finders.find("core/js/builders.js"))

    def test_workflow_form_uses_editors(self):
        self._assert_editor("admin:core_workflow_add", "workflow_actions")

    def test_formula_form_uses_editor(self):
        self._assert_editor("admin:core_formula_add", "formula", visual=False)

    def test_dynamic_logic_form_uses_editor(self):
        self._assert_editor("admin:core_dynamiclogic_add", "dynamic_logic")

    def test_custom_field_form_uses_editor(self):
        self._assert_editor("admin:core_customfield_add", "custom_field")

    def test_lead_capture_form_uses_editor(self):
        self._assert_editor("admin:crm_leadcapture_add", "lead_capture")

    def test_layout_form_uses_editor(self):
        self._assert_editor("admin:core_layout_add", "layout")

    def test_task_form_uses_reminders_builder(self):
        self._assert_editor("admin:crm_task_add", "reminders")

    def test_call_form_uses_reminders_and_recurrence(self):
        self._assert_editor("admin:crm_call_add", "reminders")
        self._assert_editor("admin:crm_call_add", "recurrence")

    def test_meeting_form_uses_recurrence_builder(self):
        self._assert_editor("admin:crm_meeting_add", "recurrence")

    def test_layout_change_form_links_to_layout_editor(self):
        layout = Layout.objects.create(
            entity_type="Task", layout_name="list", data=["name"]
        )
        self.addCleanup(layout.delete)
        response = self.client.get(
            reverse("admin:core_layout_change", args=[layout.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Open in Layout Editor")
        self.assertContains(response, "/admin/layout-editor/Task/")
