from django.test import RequestFactory, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from omacrm.core.metadata.registry import registry
from omacrm.core.models import CustomEntity, CustomField, DynamicRecord, Role, User
from omacrm.core.services import custom_entities
from omacrm.core.services.navigation import sidebar_navigation


class EntityManagerTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "em-admin", "em@example.com", "pw"
        )
        self.client.force_login(self.admin)
        self.entity = CustomEntity.objects.create(
            name="Project",
            label="Project",
            label_plural="Projects",
            icon="architecture",
            menu_order=5,
        )
        self.addCleanup(registry.invalidate)
        self.addCleanup(self._cleanup, self.entity)

    def _cleanup(self, entity):
        DynamicRecord.objects.filter(entity_type=entity.name).delete()
        custom_entities.unregister(entity)
        if entity.pk:
            entity.delete()
        registry.invalidate()

    def _request(self, user=None):
        request = RequestFactory().get("/admin/")
        request.user = user or self.admin
        return request

    def test_registry_uses_entity_properties(self):
        self.entity.stream = False
        self.entity.sort_field = "name"
        self.entity.sort_direction = "asc"
        self.entity.search_fields = "name"
        self.entity.duplicate_check_fields = "name"
        self.entity.save()
        registry.invalidate()

        entity = registry.get("Project")
        self.assertEqual(entity.icon, "architecture")
        self.assertFalse(entity.stream)
        self.assertEqual(entity.ordering, ["name"])
        self.assertEqual(entity.search_fields, ["name"])
        self.assertEqual(entity.duplicate_check_fields, ["name"])

    def test_new_entity_urls_resolve_without_manual_reload(self):
        entity = CustomEntity.objects.create(name="Contract", label="Contract")
        try:
            url = reverse("admin:core_contract_changelist")
            self.assertEqual(url, "/admin/core/contract/")
            self.assertEqual(self.client.get(url).status_code, 200)
        finally:
            DynamicRecord.objects.filter(entity_type="Contract").delete()
            custom_entities.unregister(entity)
            entity.delete()
            registry.invalidate()

    def test_sidebar_lists_custom_entity(self):
        navigation = sidebar_navigation(self._request())
        groups = {str(group["title"]): group for group in navigation}
        self.assertIn("Custom entities", groups)
        item = groups["Custom entities"]["items"][0]
        self.assertEqual(item["title"], "Projects")
        self.assertEqual(item["icon"], "architecture")
        self.assertTrue(item["link"].endswith("/admin/core/project/"))

    def test_sidebar_hides_entities_without_menu(self):
        self.entity.show_in_menu = False
        self.entity.save()
        navigation = sidebar_navigation(self._request())
        self.assertNotIn(
            "Custom entities", {str(group["title"]) for group in navigation}
        )

    def test_sidebar_respects_acl(self):
        role = Role.objects.create(
            name="No projects", data={"Project": {"read": "no"}}
        )
        staff = User.objects.create_user(
            "em-staff", "em-staff@example.com", "pw", is_staff=True
        )
        staff.roles.add(role)
        navigation = sidebar_navigation(self._request(staff))
        groups = {str(group["title"]): group for group in navigation}
        self.assertNotIn("Custom entities", groups)

    def test_sidebar_visible_for_role_users_without_entity_entry(self):
        from omacrm.core.services.acl import AclService

        role = Role.objects.create(
            name="Accounts only", data={"Account": {"read": "all"}}
        )
        staff = User.objects.create_user(
            "em-sales", "em-sales@example.com", "pw", is_staff=True
        )
        staff.roles.add(role)

        self.assertTrue(AclService.check(staff, "Project", "read"))
        self.assertFalse(AclService.check(staff, "Lead", "read"))

        navigation = sidebar_navigation(self._request(staff))
        groups = {str(group["title"]): group for group in navigation}
        self.assertIn("Custom entities", groups)
        self.assertEqual(groups["Custom entities"]["items"][0]["title"], "Projects")


class DynamicApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "api-dyn-admin", "api-dyn@example.com", "pw"
        )
        self.entity = CustomEntity.objects.create(
            name="Project", label="Project", label_plural="Projects"
        )
        CustomField.objects.create(
            entity_type="Project", name="code", field_type="varchar", label="Code"
        )
        registry.invalidate()
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.addCleanup(registry.invalidate)
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        DynamicRecord.objects.filter(entity_type="Project").delete()
        custom_entities.unregister(self.entity)
        if self.entity.pk:
            self.entity.delete()
        CustomField.objects.filter(entity_type="Project").delete()
        registry.invalidate()

    def test_list_and_create_without_restart(self):
        DynamicRecord.objects.create(
            entity_type="Project", name="Apollo", custom_data={"code": "P-1"}
        )
        response = self.client.get("/api/v1/Project/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

        response = self.client.post(
            "/api/v1/Project/",
            {"name": "Zeus", "custom_data": {"code": "P-2"}},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        record = DynamicRecord.objects.get(name="Zeus")
        self.assertEqual(record.entity_type, "Project")
        self.assertEqual(record.custom_data["code"], "P-2")

    def test_unknown_dynamic_entity_returns_404(self):
        self.assertEqual(self.client.get("/api/v1/Nope/").status_code, 404)

    def test_builtin_routes_still_work(self):
        self.assertEqual(self.client.get("/api/v1/account/").status_code, 200)
