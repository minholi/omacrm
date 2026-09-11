from django.test import TestCase
from django.urls import reverse

from omacrm.core.models import Role, User
from omacrm.crm.models import Account, Contact, Lead


class GlobalSearchTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("search-admin", "sa@example.com", "pw")
        self.client.force_login(self.admin)
        self.url = reverse("global_search")
        self.account = Account.objects.create(name="Acme Inc")
        self.contact = Contact.objects.create(
            first_name="Acme", last_name="Contact"
        )
        self.lead = Lead.objects.create(first_name="Acme", last_name="Lead")

    def test_finds_results_across_entities(self):
        response = self.client.get(self.url, {"q": "Acme"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Acme Inc")
        self.assertContains(response, "Acme Contact")
        self.assertContains(response, "Acme Lead")
        self.assertContains(response, "Accounts")
        self.assertContains(response, "Contacts")
        self.assertContains(response, "Leads")
        self.assertContains(
            response, f"/admin/crm/account/{self.account.pk}/change/"
        )

    def test_empty_query_shows_form_only(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Acme Inc")

    def test_unknown_query_returns_no_results(self):
        response = self.client.get(self.url, {"q": "zzzz-not-found"})
        self.assertContains(response, "No results found")

    def test_acl_scoping(self):
        user = User.objects.create_user("scoped", "scoped@example.com", "pw")
        role = Role.objects.create(
            name="Search scoped",
            data={"Account": {"read": "own"}},
        )
        user.roles.add(role)
        user.is_staff = True
        user.save()
        own = Account.objects.create(name="Acme Own", assigned_user=user)
        Account.objects.create(name="Acme Other")

        self.client.force_login(user)
        response = self.client.get(self.url, {"q": "Acme"})
        self.assertContains(response, "Acme Own")
        self.assertNotContains(response, "Acme Other")
        # Scopes without an explicit role level are denied.
        self.assertNotContains(response, "Acme Contact")

    def test_requires_staff(self):
        self.client.force_login(
            User.objects.create_user("plain-search", "ps@example.com", "pw")
        )
        self.assertEqual(self.client.get(self.url).status_code, 302)
