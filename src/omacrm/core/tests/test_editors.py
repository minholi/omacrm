from django.test import TestCase
from django.urls import reverse

from omacrm.core.metadata.registry import registry
from omacrm.core.models import Layout, Role, User


class LayoutEditorTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("layout-admin", "le@example.com", "pw")
        self.client.force_login(self.admin)
        self.addCleanup(registry.invalidate)
        self.addCleanup(lambda: Layout.objects.filter(entity_type="Team").delete())

    def test_index_and_form_render(self):
        self.assertEqual(self.client.get(reverse("layout_editor_index")).status_code, 200)
        response = self.client.get(
            reverse("layout_editor", kwargs={"entity_type": "Team"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "name")

    def test_save_layout(self):
        response = self.client.post(
            reverse("layout_editor", kwargs={"entity_type": "Team"}),
            {
                "list_fields": ["name", "description"],
                "detail_layout": '[{"title": "Main", "fields": ["name"]}]',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(registry.layout("Team", "list"), ["name", "description"])
        self.assertEqual(
            registry.layout("Team", "detail"),
            [{"title": "Main", "fields": ["name"]}],
        )

    def test_save_preserves_column_order(self):
        self.client.post(
            reverse("layout_editor", kwargs={"entity_type": "Team"}),
            {
                "list_fields": ["description", "name"],
                "detail_layout": "[]",
            },
        )
        self.assertEqual(registry.layout("Team", "list"), ["description", "name"])

    def test_form_has_drag_and_drop_markup(self):
        response = self.client.get(
            reverse("layout_editor", kwargs={"entity_type": "Team"})
        )
        self.assertContains(response, 'id="layout-list-fields"')
        self.assertContains(response, 'draggable="true"')

    def test_detail_sections_render_visual_editor(self):
        Layout.objects.create(
            entity_type="Team",
            layout_name="detail",
            data=[{"title": "Main", "fields": ["name"]}],
            is_custom=True,
        )
        response = self.client.get(
            reverse("layout_editor", kwargs={"entity_type": "Team"})
        )
        self.assertContains(response, 'id="detail-editor"')
        self.assertContains(response, 'id="detail-fields-palette"')
        self.assertContains(response, 'data-section')
        self.assertContains(response, 'data-section-handle')
        self.assertContains(response, 'data-dropzone')
        self.assertContains(response, 'data-remove-chip')
        self.assertContains(response, 'name="detail_layout"')
        self.assertContains(response, 'value="Main"')
        self.assertContains(response, 'data-field="name"')

    def test_invalid_field_is_rejected(self):
        self.client.post(
            reverse("layout_editor", kwargs={"entity_type": "Team"}),
            {
                "list_fields": ["name"],
                "detail_layout": '[{"title": "Main", "fields": ["does_not_exist"]}]',
            },
        )
        self.assertFalse(
            Layout.objects.filter(entity_type="Team", layout_name="detail").exists()
        )

    def test_unknown_entity_returns_404(self):
        response = self.client.get(
            reverse("layout_editor", kwargs={"entity_type": "NotAnEntity"})
        )
        self.assertEqual(response.status_code, 404)


class RoleAclEditorTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("acl-admin", "acl@example.com", "pw")
        self.client.force_login(self.admin)
        self.role = Role.objects.create(name="Access Role")

    def test_editor_renders(self):
        response = self.client.get(
            reverse("role_acl_editor", args=[self.role.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_save_scope_and_field_levels(self):
        response = self.client.post(
            reverse("role_acl_editor", args=[self.role.pk]),
            {
                "selected_entity": "Account",
                "scope__Account__read": "team",
                "scope__Account__edit": "own",
                "field__Account__phone_number": "no",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.role.refresh_from_db()
        self.assertEqual(self.role.data["Account"], {"read": "team", "edit": "own"})
        self.assertEqual(self.role.field_data["Account"], {"phone_number": "no"})

    def test_field_level_preserved_for_other_entities(self):
        self.role.field_data = {"Contact": {"email_address": "no"}}
        self.role.save(update_fields=["field_data"])

        self.client.post(
            reverse("role_acl_editor", args=[self.role.pk]),
            {
                "selected_entity": "Account",
                "scope__Account__read": "all",
                "field__Account__phone_number": "no",
            },
        )
        self.role.refresh_from_db()
        self.assertEqual(self.role.field_data["Contact"], {"email_address": "no"})
        self.assertEqual(self.role.field_data["Account"], {"phone_number": "no"})
