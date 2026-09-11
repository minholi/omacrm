from django.test import TestCase
from django.urls import reverse

from omacrm.core.models import PortalRole, User
from omacrm.crm.models import Case, Contact, KnowledgeBaseArticle


class PortalTests(TestCase):
    def setUp(self):
        self.contact = Contact.objects.create(
            first_name="Portal", last_name="User", email_address="portal@example.com"
        )
        self.user = User.objects.create_user(
            "portal", "portal@example.com", "pw", type=User.Type.PORTAL
        )
        self.contact.portal_user = self.user
        self.contact.save(update_fields=["portal_user"])

        self.other_contact = Contact.objects.create(
            first_name="Other", last_name="Person"
        )
        self.other_user = User.objects.create_user(
            "other-portal", "other@example.com", "pw", type=User.Type.PORTAL
        )
        self.other_contact.portal_user = self.other_user
        self.other_contact.save(update_fields=["portal_user"])

        self.own_case = Case.objects.create(name="My printer is broken", contact=self.contact)
        self.other_case = Case.objects.create(name="Other customer case", contact=self.other_contact)
        self.published = KnowledgeBaseArticle.objects.create(
            name="How to reset", status="Published", body="<p>Press reset.</p>"
        )
        self.draft = KnowledgeBaseArticle.objects.create(
            name="Internal draft", status="Draft", body="<p>secret</p>"
        )

    def login(self, user=None):
        self.client.force_login(user or self.user)

    def test_login_page_renders(self):
        response = self.client.get(reverse("portal:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign in")

    def test_dashboard_requires_login(self):
        self.assertEqual(
            self.client.get(reverse("portal:dashboard")).status_code, 302
        )

    def test_dashboard_renders(self):
        self.login()
        response = self.client.get(reverse("portal:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My printer is broken")
        self.assertContains(response, "How to reset")

    def test_case_list_only_shows_own_cases(self):
        self.login()
        response = self.client.get(reverse("portal:case_list"))
        self.assertContains(response, "My printer is broken")
        self.assertNotContains(response, "Other customer case")

    def test_case_detail_permissions(self):
        self.login()
        self.assertEqual(
            self.client.get(
                reverse("portal:case_detail", args=[self.own_case.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse("portal:case_detail", args=[self.other_case.pk])
            ).status_code,
            403,
        )

    def test_case_create_sets_contact_and_status(self):
        self.login()
        response = self.client.post(
            reverse("portal:case_create"),
            {
                "name": "Cannot log in",
                "description": "Password reset needed",
                "priority": "High",
                "type": "Question",
            },
        )
        self.assertEqual(response.status_code, 302)
        case = Case.objects.get(name="Cannot log in")
        self.assertEqual(case.contact, self.contact)
        self.assertEqual(case.status, Case.Status.NEW)
        self.assertEqual(case.created_by, self.user)

    def test_kb_only_published(self):
        self.login()
        response = self.client.get(reverse("portal:kb_list"))
        self.assertContains(response, "How to reset")
        self.assertNotContains(response, "Internal draft")

        self.assertEqual(
            self.client.get(
                reverse("portal:kb_detail", args=[self.published.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("portal:kb_detail", args=[self.draft.pk])).status_code,
            403,
        )

    def test_portal_role_can_restrict_access(self):
        role = PortalRole.objects.create(
            name="Restricted",
            data={"Case": {"read": "no"}, "KnowledgeBaseArticle": {"read": "no"}},
        )
        self.user.portal_roles.add(role)
        self.login()
        self.assertNotContains(
            self.client.get(reverse("portal:case_list")), "My printer is broken"
        )
        self.assertEqual(
            self.client.get(
                reverse("portal:case_detail", args=[self.own_case.pk])
            ).status_code,
            403,
        )

    def test_portal_user_cannot_access_admin_or_api(self):
        self.login()
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        self.assertEqual(self.client.get("/api/v1/case/").status_code, 403)
