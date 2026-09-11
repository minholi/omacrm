from django.test import RequestFactory, TestCase
from django.urls import reverse

from omacrm.core.models import Role, SavedFilter, User
from omacrm.core.services.command_palette import command_search


class CommandPaletteTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin = User.objects.create_superuser(
            "palette", "palette@example.com", "pw"
        )
        self.staff = User.objects.create_user(
            "palette-staff", "palette-staff@example.com", "pw", is_staff=True
        )

    def _request(self, user):
        request = self.factory.get("/admin/search/")
        request.user = user
        return request

    def test_static_commands_match(self):
        results = command_search(self._request(self.admin), "cal")
        self.assertIn("Calendar", [result.title for result in results])

    def test_no_match_returns_empty(self):
        self.assertEqual(command_search(self._request(self.admin), "zzzz"), [])

    def test_entity_shortcuts_respect_permissions(self):
        results = command_search(self._request(self.admin), "account")
        self.assertIn("Accounts", [result.title for result in results])
        self.assertIn(
            reverse("admin:crm_account_changelist"),
            [result.link for result in results],
        )

        role = Role.objects.create(
            name="No accounts", data={"Account": {"read": "no"}}
        )
        self.staff.roles.add(role)
        results = command_search(self._request(self.staff), "account")
        self.assertNotIn("Accounts", [result.title for result in results])

    def test_saved_filter_entry(self):
        SavedFilter.objects.create(
            user=self.admin,
            entity_type="Account",
            name="Hot accounts",
            params={"stage__exact": "Proposal"},
        )
        results = command_search(self._request(self.admin), "hot")
        match = next(result for result in results if result.title == "Hot accounts")
        self.assertIn(reverse("admin:crm_account_changelist"), match.link)
        self.assertIn("stage__exact=Proposal", match.link)


class CommandPaletteIntegrationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "palette-admin", "palette-admin@example.com", "pw"
        )
        self.client.force_login(self.admin)

    def test_admin_search_includes_custom_commands(self):
        response = self.client.get("/admin/search/", {"s": "calendar"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Calendar")
