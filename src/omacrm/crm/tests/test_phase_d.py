import tempfile
from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from djmoney.money import Money

from omacrm.core.models import Currency, Note, User
from omacrm.core.services.jobs import JobRunner, schedule
from omacrm.crm.models import (
    Case,
    Contact,
    Document,
    DocumentFolder,
    EmailTemplate,
    KnowledgeBaseArticle,
    Lead,
    Opportunity,
)
from omacrm.crm.services import render_email_template


class CaseTests(TestCase):
    def test_auto_numbering(self):
        first = Case.objects.create(name="First")
        second = Case.objects.create(name="Second")
        self.assertEqual(second.number, first.number + 1)
        self.assertEqual(str(second), f"#{second.number} Second")


class KnowledgeBaseTests(TestCase):
    def test_body_plain_is_derived(self):
        article = KnowledgeBaseArticle.objects.create(
            name="Article", body="<p>Hello <b>world</b></p>"
        )
        self.assertEqual(article.body_plain, "Hello world")

    def test_status_job_publishes_and_archives(self):
        today = timezone.localdate()
        draft = KnowledgeBaseArticle.objects.create(
            name="Draft article",
            publish_date=today - timedelta(days=1),
        )
        expired = KnowledgeBaseArticle.objects.create(
            name="Expired article",
            status=KnowledgeBaseArticle.Status.PUBLISHED,
            expiration_date=today - timedelta(days=1),
        )
        schedule("crm.control_kb_article_status")
        JobRunner.run_pending()

        draft.refresh_from_db()
        expired.refresh_from_db()
        self.assertEqual(draft.status, KnowledgeBaseArticle.Status.PUBLISHED)
        self.assertEqual(expired.status, KnowledgeBaseArticle.Status.ARCHIVED)


class DocumentTests(TestCase):
    def test_document_with_file_and_folder(self):
        with tempfile.TemporaryDirectory() as media_root, override_settings(
            MEDIA_ROOT=media_root
        ):
            folder = DocumentFolder.objects.create(name="Contracts")
            document = Document.objects.create(
                name="Contract",
                folder=folder,
                file=SimpleUploadedFile(
                    "contract.txt", b"terms", content_type="text/plain"
                ),
            )
            self.assertTrue(document.file.name.endswith("contract.txt"))
            self.assertEqual(folder.documents.count(), 1)


class ConvertedAmountTests(TestCase):
    def setUp(self):
        Currency.objects.update_or_create(
            code="EUR", defaults={"rate": Decimal("0.9")}
        )

    def test_opportunity_amount_converted(self):
        opportunity = Opportunity.objects.create(
            name="Euro Deal", amount=Money(100, "EUR")
        )
        opportunity.refresh_from_db()
        self.assertEqual(opportunity.amount_converted, Decimal("90.00"))

    def test_lead_amount_converted(self):
        lead = Lead.objects.create(
            first_name="Euro", last_name="Lead", opportunity_amount=Money(200, "EUR")
        )
        lead.refresh_from_db()
        self.assertEqual(lead.opportunity_amount_converted, Decimal("180.00"))


class EmailTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("mail-admin", "mail@example.com", "pw")
        self.contact = Contact.objects.create(
            first_name="Jane", last_name="Mail", email_address="jane@example.com"
        )
        self.template = EmailTemplate.objects.create(
            name="Welcome",
            subject="Hello {{ name }}",
            source="<p>Dear {{ name }}, welcome!</p>",
            source_format="html",
        )

    def test_render_template(self):
        subject, body = render_email_template(self.template, self.contact)
        self.assertEqual(subject, "Hello Jane Mail")
        self.assertIn("Dear Jane Mail", body)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_send_email_creates_note(self):
        from omacrm.crm.services import send_email

        note, sent = send_email(
            self.contact, template=self.template, user=self.admin
        )
        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["jane@example.com"])
        self.assertEqual(note.type, Note.Type.EMAIL)
        self.assertEqual(note.data["subject"], "Hello Jane Mail")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_send_email_admin_action(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            f"/admin/crm/contact/{self.contact.pk}/send_email_action/",
            {
                "_form_submitted": "on",
                "template": self.template.pk,
                "to_email": "",
                "subject": "",
                "body": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(
            Note.objects.filter(
                parent_id=self.contact.pk, type=Note.Type.EMAIL
            ).exists()
        )


class PhaseDAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("phase-d", "phased@example.com", "pw")
        self.client.force_login(self.admin)

    def test_changelists_render(self):
        for name in (
            "admin:crm_case_changelist",
            "admin:crm_knowledgebasearticle_changelist",
            "admin:crm_knowledgebasecategory_changelist",
            "admin:crm_document_changelist",
            "admin:crm_documentfolder_changelist",
            "admin:crm_emailtemplate_changelist",
            "admin:core_currency_changelist",
        ):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)

    def test_sidebar_links_present(self):
        response = self.client.get(reverse("admin:index"))
        for name in ("crm_case_changelist", "crm_document_changelist"):
            self.assertContains(response, reverse(f"admin:{name}"))
