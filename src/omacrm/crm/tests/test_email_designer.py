from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from constance.test import override_config

from omacrm.core.models import User
from omacrm.crm.models import Contact, EmailTemplate
from omacrm.crm.services.email import (
    MERGE_TAGS,
    prepare_email_html,
    render_email_template,
    send_email,
)


class RenderContextTests(TestCase):
    def setUp(self):
        self.contact = Contact.objects.create(
            first_name="Jane",
            last_name="Mail",
            email_address="jane@example.com",
            custom_data={"tier": "Gold"},
        )

    def test_render_template_includes_custom_fields(self):
        template = EmailTemplate(
            name="Context",
            subject="{{ company_name }} — {{ custom.tier }}",
            source="<p>{{ name }} ({{ custom.tier }})</p>",
            source_format="html",
        )
        subject, body = render_email_template(template, self.contact)
        self.assertEqual(subject, "OmaCRM — Gold")
        self.assertIn("Jane Mail (Gold)", body)

    def test_merge_tags_have_tokens_and_labels(self):
        for tag in MERGE_TAGS:
            self.assertIn("token", tag)
            self.assertIn("label", tag)
            self.assertTrue(tag["token"].startswith("{{"))


class EmailTemplateValidationTests(TestCase):
    def test_new_template_defaults_to_starter_mjml_source(self):
        template = EmailTemplate()
        self.assertIn("<mjml>", template.source)
        self.assertIn("{{ name }}", template.source)
        self.assertIn("{{ company_name }}", template.source)
        self.assertEqual(template.source_format, "mjml")
        self.assertEqual(template.body, "")

    def test_clean_passes_for_starter_source(self):
        template = EmailTemplate(name="Default", subject="Hi")
        template.clean()

    def test_clean_raises_for_empty_source(self):
        template = EmailTemplate(name="Empty", subject="Hi", source="   ")
        with self.assertRaises(ValidationError) as caught:
            template.clean()
        self.assertIn("source", caught.exception.message_dict)

    def test_render_email_template_returns_subject_and_body(self):
        contact = Contact.objects.create(
            first_name="Jane", last_name="Mail", email_address="jane@example.com"
        )
        template = EmailTemplate(
            name="Contract",
            subject="Hi {{ name }}",
            source="<p>Hello {{ name }}</p>",
            source_format="html",
        )
        subject, body = render_email_template(template, contact)
        self.assertEqual(subject, "Hi Jane Mail")
        self.assertIn("Hello Jane Mail", body)


class PrepareEmailHtmlTests(TestCase):
    def test_inlines_styles_and_builds_text(self):
        html = "<style>p{color:red}</style><p>Hello</p>"
        inlined, text = prepare_email_html(html)
        self.assertRegex(inlined, r'style="color:\s*red')
        self.assertIn("Hello", text)
        self.assertNotIn("<p>", text)

    def test_plain_text_stays_unchanged(self):
        html, text = prepare_email_html("Dear Jane, welcome!")
        self.assertEqual(html, "Dear Jane, welcome!")
        self.assertEqual(text, "Dear Jane, welcome!")

    @override_config(public_base_url="https://crm.example.com")
    def test_absolutizes_relative_urls(self):
        html = (
            '<a href="/records/1">open</a>'
            '<img src="/media/email-assets/logo.png">'
            "<div style=\"background: url('/media/bg.png')\"></div>"
        )
        inlined, _ = prepare_email_html(html)
        self.assertIn('href="https://crm.example.com/records/1"', inlined)
        self.assertIn('src="https://crm.example.com/media/email-assets/logo.png"', inlined)
        self.assertIn("url('https://crm.example.com/media/bg.png')", inlined)

    @override_config(public_base_url="https://crm.example.com")
    def test_keeps_absolute_and_protocol_relative_urls(self):
        html = (
            '<a href="https://other.example.com/x">a</a>'
            '<script src="//cdn.example.com/app.js"></script>'
            '<a href="#anchor">b</a>'
        )
        inlined, _ = prepare_email_html(html)
        self.assertIn('href="https://other.example.com/x"', inlined)
        self.assertIn('src="//cdn.example.com/app.js"', inlined)
        self.assertIn('href="#anchor"', inlined)

    @override_config(public_base_url="")
    def test_relative_urls_untouched_without_base_url(self):
        html = '<img src="/media/logo.png">'
        inlined, _ = prepare_email_html(html)
        self.assertIn('src="/media/logo.png"', inlined)


class SendEmailInliningTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("inline-admin", "i@example.com", "pw")
        self.contact = Contact.objects.create(
            first_name="Jane", last_name="Mail", email_address="jane@example.com"
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_send_plain_body_sets_text_and_html_alternatives(self):
        send_email(self.contact, subject="Hi", body="Dear Jane", user=self.admin)
        message = mail.outbox[0]
        self.assertEqual(message.body, "Dear Jane")
        html_alternative = message.alternatives[0][0]
        self.assertIn("Dear Jane", html_alternative)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_send_html_body_inlines_styles(self):
        template = EmailTemplate.objects.create(
            name="Styled",
            subject="Hello {{ name }}",
            source="<style>p{color:blue}</style><p>Dear {{ name }}</p>",
            source_format="html",
        )
        send_email(self.contact, template=template, user=self.admin)
        message = mail.outbox[0]
        html_alternative = message.alternatives[0][0]
        self.assertRegex(html_alternative, r'style="color:\s*blue')
        self.assertIn("Dear Jane Mail", html_alternative)
        self.assertIn("Dear Jane Mail", message.body)


class EmailTemplatePreviewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("preview", "p@example.com", "pw")
        self.contact = Contact.objects.create(
            first_name="Jane", last_name="Mail", email_address="jane@example.com"
        )
        self.template = EmailTemplate.objects.create(
            name="Preview Me",
            subject="Hi {{ name }}",
            source="<p>Hello {{ name }}</p>",
            source_format="html",
        )

    def test_preview_renders_merge_tags(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("email_template_preview", args=[self.template.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/html")
        self.assertIn("Hello Jane Mail", response.content.decode())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_test_send_delivers_to_requested_address(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("email_template_test_send", args=[self.template.pk]),
            {"to_email": "qa@example.com"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["to"], "qa@example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["qa@example.com"])
        self.assertIn("Hello Jane Mail", mail.outbox[0].body)


class EmailTemplateAdminReadOnlyTests(TestCase):
    original_body = "<p>Original body</p>"
    original_source = "<p>Original source</p>"

    def setUp(self):
        self.admin = User.objects.create_superuser(
            "template-admin", "template@example.com", "pw"
        )
        self.client.force_login(self.admin)
        self.template = EmailTemplate.objects.create(
            name="Locked",
            subject="Original subject",
            body=self.original_body,
            source=self.original_source,
            source_format="html",
        )
        self.template.refresh_from_db()
        self.change_url = reverse(
            "admin:crm_emailtemplate_change", args=[self.template.pk]
        )

    def test_change_form_renders_body_and_source_read_only(self):
        response = self.client.get(self.change_url)
        self.assertEqual(response.status_code, 200)
        for name in ("body", "source", "source_format"):
            self.assertNotContains(response, f'name="{name}"')
        self.assertContains(response, "Original source")

    def test_tampered_compiled_values_are_not_saved(self):
        stored_body = self.template.body
        stored_source = self.template.source
        response = self.client.post(
            self.change_url,
            {
                "name": self.template.name,
                "subject": self.template.subject,
                "is_active": "on",
                "body": "<p>Tampered body</p>",
                "source": "tampered source",
                "source_format": "mjml",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.template.refresh_from_db()
        self.assertEqual(self.template.body, stored_body)
        self.assertEqual(self.template.source, stored_source)
        self.assertEqual(self.template.source_format, "html")

    def test_editable_fields_persist(self):
        response = self.client.post(
            self.change_url,
            {
                "name": "Renamed",
                "subject": "New subject",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.template.refresh_from_db()
        self.assertEqual(self.template.name, "Renamed")
        self.assertEqual(self.template.subject, "New subject")
        self.assertFalse(self.template.is_active)
