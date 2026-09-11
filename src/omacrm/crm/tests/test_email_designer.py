import json
import shutil
import tempfile
from io import BytesIO
from pathlib import Path

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.contrib.staticfiles import finders
from django.urls import reverse
from constance.test import override_config
from PIL import Image

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
            body="<p>{{ name }} ({{ custom.tier }})</p>",
        )
        subject, body = render_email_template(template, self.contact)
        self.assertEqual(subject, "OmaCRM — Gold")
        self.assertIn("Jane Mail (Gold)", body)

    def test_merge_tags_have_tokens_and_labels(self):
        for tag in MERGE_TAGS:
            self.assertIn("token", tag)
            self.assertIn("label", tag)
            self.assertTrue(tag["token"].startswith("{{"))


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
            body="<style>p{color:blue}</style><p>Dear {{ name }}</p>",
        )
        send_email(self.contact, template=template, user=self.admin)
        message = mail.outbox[0]
        html_alternative = message.alternatives[0][0]
        self.assertRegex(html_alternative, r'style="color:\s*blue')
        self.assertIn("Dear Jane Mail", html_alternative)
        self.assertIn("Dear Jane Mail", message.body)


class VendorAssetTests(TestCase):
    def test_grapesjs_assets_are_vendored(self):
        for path in (
            "vendor/grapesjs/grapes.min.js",
            "vendor/grapesjs/grapes.min.css",
            "vendor/grapesjs/grapesjs-preset-newsletter.min.js",
        ):
            self.assertIsNotNone(finders.find(path), path)


class EmailDesignerViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("designer", "d@example.com", "pw")
        self.staff = User.objects.create_user(
            "designer-staff", "s@example.com", "pw", is_staff=True
        )
        self.contact = Contact.objects.create(
            first_name="Jane", last_name="Mail", email_address="jane@example.com"
        )
        self.template = EmailTemplate.objects.create(
            name="Design Me",
            subject="Hi {{ name }}",
            body="<p>Hello {{ name }}</p>",
        )
        self.design_url = reverse(
            "email_template_design", args=[self.template.pk]
        )
        self.save_url = reverse(
            "email_template_design_save", args=[self.template.pk]
        )

    def test_editor_requires_login(self):
        response = self.client.get(self.design_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_editor_requires_change_permission(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.design_url)
        self.assertEqual(response.status_code, 403)

    def test_editor_renders_grapesjs_and_config(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.design_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "vendor/grapesjs/grapes.min.js")
        self.assertContains(
            response, "vendor/grapesjs/grapesjs-preset-newsletter.min.js"
        )
        self.assertContains(response, "email-designer-config")
        self.assertContains(response, "{{ name }}")

    def test_admin_change_form_has_design_action(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("admin:crm_emailtemplate_change", args=[self.template.pk])
        )
        action_url = reverse(
            "admin:crm_emailtemplate_open_designer", args=[self.template.pk]
        )
        self.assertContains(response, "Design")
        self.assertContains(response, action_url)

    def test_design_action_redirects_to_editor(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("admin:crm_emailtemplate_open_designer", args=[self.template.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], self.design_url)

    def test_save_updates_design_and_inlines_body(self):
        self.client.force_login(self.admin)
        payload = {
            "design": {"pages": []},
            "html": "<style>p{color:green}</style><p>Hello {{ name }}</p>",
            "css": "",
        }
        response = self.client.post(
            self.save_url, data=json.dumps(payload), content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

        self.template.refresh_from_db()
        self.assertEqual(self.template.design, {"pages": []})
        self.assertRegex(self.template.body, r'style="color:\s*green')
        self.assertIn("{{ name }}", self.template.body)

    def test_save_rejects_invalid_json(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            self.save_url, data="{not json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_save_requires_post(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.save_url).status_code, 405)

    def test_save_enforces_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        response = client.post(
            self.save_url, data="{}", content_type="application/json"
        )
        self.assertEqual(response.status_code, 403)

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


class EmailAssetUploadTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("assets", "a@example.com", "pw")
        self.staff = User.objects.create_user(
            "assets-staff", "as@example.com", "pw", is_staff=True
        )
        self.upload_url = reverse("email_asset_upload")
        self.media_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media_dir, ignore_errors=True)
        media_override = override_settings(MEDIA_ROOT=self.media_dir)
        media_override.enable()
        self.addCleanup(media_override.disable)

    def _png(self):
        buffer = BytesIO()
        Image.new("RGB", (2, 2), "white").save(buffer, format="PNG")
        return SimpleUploadedFile(
            "logo.png", buffer.getvalue(), content_type="image/png"
        )

    def test_upload_requires_login(self):
        response = self.client.post(self.upload_url, {"files": self._png()})
        self.assertEqual(response.status_code, 302)

    def test_upload_requires_change_permission(self):
        self.client.force_login(self.staff)
        response = self.client.post(self.upload_url, {"files": self._png()})
        self.assertEqual(response.status_code, 403)

    def test_upload_rejects_non_image(self):
        self.client.force_login(self.admin)
        upload = SimpleUploadedFile(
            "notes.txt", b"secret", content_type="text/plain"
        )
        response = self.client.post(self.upload_url, {"files": upload})
        self.assertEqual(response.status_code, 400)

    def test_upload_rejects_fake_image(self):
        self.client.force_login(self.admin)
        upload = SimpleUploadedFile(
            "fake.png", b"not an image", content_type="image/png"
        )
        response = self.client.post(self.upload_url, {"files": upload})
        self.assertEqual(response.status_code, 400)

    def test_upload_stores_image_and_returns_asset(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.upload_url, {"files": self._png()})
        self.assertEqual(response.status_code, 200)
        asset = response.json()["data"][0]
        self.assertEqual(asset["name"], "logo.png")
        self.assertTrue(asset["src"].startswith("/media/email-assets/"))
        self.assertTrue(asset["src"].endswith(".png"))
        self.assertTrue(
            (Path(self.media_dir) / asset["src"].replace("/media/", "")).exists()
        )

    def test_upload_requires_post(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.upload_url).status_code, 405)
