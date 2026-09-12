from importlib import import_module

from django.apps import apps as django_apps
from django.core.exceptions import ValidationError
from django.test import TestCase

from omacrm.crm.models import Contact, EmailTemplate
from omacrm.crm.services.email import (
    CompileResult,
    compile_email_source,
    prepare_email_html,
    render_email_template,
)

VALID_MJML = """
<mjml>
  <mj-body>
    <mj-section>
      <mj-column>
        <mj-text>Hello {{ name }}</mj-text>
        <mj-button href="https://example.com">Open</mj-button>
      </mj-column>
    </mj-section>
  </mj-body>
</mjml>
"""


class CompileEmailSourceTests(TestCase):
    def test_mjml_source_compiles_to_responsive_html(self):
        result = compile_email_source(VALID_MJML, "mjml")
        self.assertIsNone(result.error)
        self.assertIn("<table", result.html)
        self.assertIn("@media", result.html)

    def test_unknown_mjml_tag_is_reported(self):
        source = VALID_MJML.replace(
            "</mj-text>", "</mj-text><mj-naoexiste>x</mj-naoexiste>"
        )
        result = compile_email_source(source, "mjml")
        self.assertIsNotNone(result.error)
        self.assertIn("mj-naoexiste", result.error)

    def test_broken_markup_is_reported(self):
        result = compile_email_source("<mjml><mj-body><mj-section>", "mjml")
        self.assertIsNotNone(result.error)

    def test_invalid_django_template_is_reported(self):
        result = compile_email_source("<mjml>{% if %}</mjml>", "mjml")
        self.assertIsNotNone(result.error)

    def test_html_source_is_returned_unchanged(self):
        source = "<style>p{color:red}</style><p>Hello</p>"
        result = compile_email_source(source, "html")
        self.assertEqual(result, CompileResult(html=source))

    def test_html_output_still_flows_through_premailer(self):
        source = "<style>p{color:red}</style><p>Hello</p>"
        result = compile_email_source(source, "html")
        inlined, text = prepare_email_html(result.html)
        self.assertRegex(inlined, r'style="color:\s*red')
        self.assertIn("Hello", text)


class EmailTemplateCompileTests(TestCase):
    def test_save_compiles_mjml_body(self):
        template = EmailTemplate.objects.create(
            name="Compiled",
            subject="Hi {{ name }}",
            source=VALID_MJML,
            source_format="mjml",
        )
        self.assertIn("<table", template.body)
        self.assertIn("@media", template.body)

    def test_save_uses_html_source_as_body(self):
        template = EmailTemplate.objects.create(
            name="Html source",
            subject="Hi",
            source="<p>Hello</p>",
            source_format="html",
        )
        self.assertEqual(template.body, "<p>Hello</p>")

    def test_clean_passes_for_valid_mjml(self):
        template = EmailTemplate(
            name="Valid", subject="Hi", source=VALID_MJML, source_format="mjml"
        )
        template.clean()

    def test_clean_raises_for_unknown_tag(self):
        template = EmailTemplate(
            name="Unknown",
            subject="Hi",
            source=VALID_MJML.replace(
                "</mj-text>", "</mj-text><mj-naoexiste>x</mj-naoexiste>"
            ),
            source_format="mjml",
        )
        with self.assertRaises(ValidationError) as caught:
            template.clean()
        self.assertIn("source", caught.exception.message_dict)
        self.assertIn("mj-naoexiste", str(caught.exception))

    def test_clean_raises_for_invalid_django_template(self):
        template = EmailTemplate(
            name="Bad template",
            subject="Hi",
            source="<mjml>{% if %}</mjml>",
            source_format="mjml",
        )
        with self.assertRaises(ValidationError) as caught:
            template.clean()
        self.assertIn("source", caught.exception.message_dict)


class BackfillMigrationTests(TestCase):
    def test_migration_fills_source_and_source_format(self):
        template = EmailTemplate.objects.create(
            name="Legacy", subject="Hi", body="<p>Legacy</p>"
        )
        self.assertEqual(template.source, "")

        migration = import_module(
            "omacrm.crm.migrations.0011_backfill_emailtemplate_source"
        )
        migration.backfill_email_source(django_apps, None)

        template.refresh_from_db()
        self.assertEqual(template.source, "<p>Legacy</p>")
        self.assertEqual(template.source_format, "html")


class RenderEmailTemplateTests(TestCase):
    def setUp(self):
        self.contact = Contact.objects.create(
            first_name="Jane", last_name="Mail", email_address="jane@example.com"
        )

    def test_renders_html_source(self):
        template = EmailTemplate.objects.create(
            name="Html source",
            subject="Hi {{ name }}",
            source="<p>Hello {{ name }}</p>",
            source_format="html",
        )
        subject, body = render_email_template(template, self.contact)
        self.assertEqual(subject, "Hi Jane Mail")
        self.assertIn("Hello Jane Mail", body)

    def test_renders_mjml_source_with_record_context(self):
        template = EmailTemplate.objects.create(
            name="Mjml source",
            subject="Hi {{ name }}",
            source=VALID_MJML,
            source_format="mjml",
        )
        subject, body = render_email_template(template, self.contact)
        self.assertEqual(subject, "Hi Jane Mail")
        self.assertIn("Hello Jane Mail", body)
        self.assertNotIn("<mj-", body)

    def test_falls_back_to_body_when_source_empty(self):
        template = EmailTemplate.objects.create(
            name="Body only", subject="Hi", body="<p>Body {{ name }}</p>"
        )
        _subject, body = render_email_template(template, self.contact)
        self.assertIn("Body Jane Mail", body)

    def test_mj_all_and_mj_class_are_valid_mjml_tags(self):
        """mj-all/mj-class are official MJML tags, used inside mj-attributes.

        They were missing from the whitelist once and every template that used
        them was rejected as "Unknown MJML tag(s)".
        """
        template = EmailTemplate.objects.create(
            name="Mjml attributes",
            subject="Hi",
            source_format="mjml",
            source=(
                "<mjml><mj-head><mj-attributes>"
                '<mj-all font-family="Helvetica" />'
                '<mj-class name="brand" color="#ff0000" />'
                "</mj-attributes></mj-head><mj-body><mj-section><mj-column>"
                '<mj-text mj-class="brand">Ola {{ name }}</mj-text>'
                "</mj-column></mj-section></mj-body></mjml>"
            ),
        )
        _subject, body = render_email_template(template, self.contact)
        self.assertIn("Ola Jane Mail", body)
        self.assertNotIn("<mj-", body)
