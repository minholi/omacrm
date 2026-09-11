import tempfile

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse

from omacrm.core.models import PortalRole, User
from omacrm.crm.models import (
    Account,
    Case,
    Contact,
    Document,
    DocumentFolder,
    KnowledgeBaseArticle,
)


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


MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class PortalProfileDocumentTests(TestCase):
    def setUp(self):
        self.account = Account.objects.create(name="Acme")
        self.contact = Contact.objects.create(
            first_name="Portal",
            last_name="User",
            email_address="portal2@example.com",
            account=self.account,
        )
        self.user = User.objects.create_user(
            "portal2", "portal2@example.com", "pw", type=User.Type.PORTAL
        )
        self.contact.portal_user = self.user
        self.contact.save(update_fields=["portal_user"])

        self.other_contact = Contact.objects.create(
            first_name="Other", last_name="Person"
        )

        self.contact_doc = self._document("Contract", contact=self.contact)
        self.account_doc = self._document("NDA", account=self.account)
        self.other_doc = self._document("Secret", contact=self.other_contact)
        self.draft_doc = self._document("Draft", contact=self.contact, status="Draft")

    def _document(self, name, contact=None, account=None, status="Active"):
        document = Document.objects.create(name=name, status=status)
        if contact is not None:
            document.contacts.add(contact)
        if account is not None:
            document.accounts.add(account)
        document.file.save(f"{name}.txt", ContentFile(f"content of {name}".encode()))
        return document

    def login(self):
        self.client.force_login(self.user)

    def test_documents_requires_login(self):
        self.assertEqual(self.client.get(reverse("portal:documents")).status_code, 302)

    def test_documents_list_scoped_to_contact_and_account(self):
        self.login()
        response = self.client.get(reverse("portal:documents"))
        self.assertContains(response, "Contract")
        self.assertContains(response, "NDA")
        self.assertNotContains(response, "Secret")
        self.assertNotContains(response, "Draft")

    def test_document_download_permissions(self):
        self.login()
        response = self.client.get(
            reverse("portal:document_download", args=[self.contact_doc.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"content of Contract")

        self.assertEqual(
            self.client.get(
                reverse("portal:document_download", args=[self.other_doc.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse("portal:document_download", args=[self.draft_doc.pk])
            ).status_code,
            403,
        )

    def test_documents_respect_portal_role(self):
        role = PortalRole.objects.create(
            name="No docs", data={"Document": {"read": "no"}}
        )
        self.user.portal_roles.add(role)
        self.login()
        response = self.client.get(reverse("portal:documents"))
        self.assertNotContains(response, "Contract")
        self.assertEqual(
            self.client.get(
                reverse("portal:document_download", args=[self.contact_doc.pk])
            ).status_code,
            403,
        )

    def test_profile_update_syncs_contact_and_user_email(self):
        self.login()
        response = self.client.get(reverse("portal:profile"))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("portal:profile"),
            {
                "salutation": "",
                "first_name": "New",
                "last_name": "Name",
                "email_address": "new@example.com",
                "phone_number": "+15551234567",
                "title": "CTO",
                "address_street": "1 Main St",
                "address_city": "Springfield",
                "address_state": "IL",
                "address_postal_code": "62701",
                "address_country": "United States",
            },
        )
        self.assertEqual(response.status_code, 302)

        self.contact.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.contact.name, "New Name")
        self.assertEqual(self.contact.title, "CTO")
        self.assertEqual(self.contact.address_city, "Springfield")
        self.assertEqual(self.user.email, "new@example.com")

    def test_password_change(self):
        self.login()
        response = self.client.post(
            reverse("portal:password_change"),
            {
                "old_password": "pw",
                "new_password1": "new-pass-12345",
                "new_password2": "new-pass-12345",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("new-pass-12345"))
