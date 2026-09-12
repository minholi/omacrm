import json
import re
from pathlib import Path

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from omacrm.core.models import User
from omacrm.crm.admin_views import _email_blocks
from omacrm.crm.models import EmailTemplate
from omacrm.crm.services.email import MJML_TAGS, compile_email_source

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

BROKEN_MJML = "<mjml><mj-body><mj-section>"


class EmailBlockTests(TestCase):
    def test_blocks_are_available_and_labeled(self):
        blocks = _email_blocks()
        self.assertTrue(blocks)
        self.assertLessEqual(len(blocks), 6)
        self.assertIn("base", {block["id"] for block in blocks})
        for block in blocks:
            self.assertTrue(block["label"])
            self.assertTrue(block["content"].strip())
            self.assertIn("mj-", block["content"])

    def test_base_block_compiles(self):
        base = next(block for block in _email_blocks() if block["id"] == "base")
        result = compile_email_source(base["content"], "mjml")
        self.assertIsNone(result.error)
        self.assertIn("<table", result.html)


class EmailTemplateAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "source-admin", "sa@example.com", "pw"
        )
        self.template = EmailTemplate.objects.create(
            name="Admin template", subject="Hi", body="<p>Hello</p>"
        )

    def test_admin_change_form_has_code_editor_action(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("admin:crm_emailtemplate_change", args=[self.template.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit code")
        self.assertContains(
            response,
            reverse(
                "admin:crm_emailtemplate_open_source_editor",
                args=[self.template.pk],
            ),
        )

    def test_code_editor_action_redirects_to_editor(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse(
                "admin:crm_emailtemplate_open_source_editor",
                args=[self.template.pk],
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse("email_template_source", args=[self.template.pk]),
        )


class EmailTemplateSourceViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "editor-admin", "ea@example.com", "pw"
        )
        self.staff = User.objects.create_user(
            "editor-staff", "es@example.com", "pw", is_staff=True
        )
        self.template = EmailTemplate.objects.create(
            name="Source me",
            subject="Hi {{ name }}",
            source=VALID_MJML,
            source_format="mjml",
        )
        self.source_url = reverse("email_template_source", args=[self.template.pk])
        self.compile_url = reverse(
            "email_template_compile", args=[self.template.pk]
        )
        self.save_url = reverse(
            "email_template_source_save", args=[self.template.pk]
        )

    def _post_json(self, url, payload):
        return self.client.post(
            url, data=json.dumps(payload), content_type="application/json"
        )

    def test_editor_requires_login(self):
        response = self.client.get(self.source_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_editor_requires_change_permission(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.source_url).status_code, 403)

    def test_editor_returns_200_with_assets_and_config(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.source_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "crm/js/email-source-editor.js")
        self.assertContains(response, "crm/css/email-source-editor.css")
        self.assertContains(
            response, "vendor/codemirror/codemirror6.bundle.js"
        )
        self.assertContains(response, 'id="ese-config"')
        self.assertContains(response, "ese-format")
        self.assertContains(response, "Mobile 375px")
        self.assertContains(response, "{{ name }}")

    def test_editor_renders_inside_admin_layout(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.source_url)
        self.assertTemplateUsed(response, "admin/base.html")
        self.assertContains(response, 'id="nav-sidebar"')
        self.assertContains(response, "unfold/js/app.js")
        self.assertContains(response, "switchTheme")

    def test_editor_missing_template_returns_404(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("email_template_source", args=[999999])
        )
        self.assertEqual(response.status_code, 404)

    def test_editor_script_follows_admin_theme(self):
        script = finders.find("crm/js/email-source-editor.js")
        self.assertIsNotNone(script)
        content = Path(script).read_text(encoding="utf-8")
        self.assertIn("CM.oneDark", content)
        self.assertIn("themeCompartment", content)
        self.assertIn("MutationObserver", content)
        self.assertIn("(prefers-color-scheme: dark)", content)

    def test_editor_css_uses_unfold_theme_colours(self):
        stylesheet = finders.find("crm/css/email-source-editor.css")
        self.assertIsNotNone(stylesheet)
        content = Path(stylesheet).read_text(encoding="utf-8")
        self.assertIn("var(--color-", content)
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b", content))

    def test_editor_exposes_mjml_whitelist_and_merge_tags(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.source_url)
        config = response.context["source_editor_config"]
        self.assertEqual(config["mjmlTags"], sorted(MJML_TAGS))
        self.assertIn("mj-section", config["mjmlTags"])
        self.assertTrue(
            any(tag["token"] == "{{ name }}" for tag in config["mergeTags"])
        )

    def test_editor_has_no_merge_tag_or_block_dropdowns(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.source_url)
        self.assertNotContains(response, 'id="ese-merge-tag"')
        self.assertNotContains(response, 'id="ese-block"')

    def test_compile_requires_login(self):
        response = self._post_json(
            self.compile_url, {"source": VALID_MJML, "source_format": "mjml"}
        )
        self.assertEqual(response.status_code, 302)

    def test_compile_requires_change_permission(self):
        self.client.force_login(self.staff)
        response = self._post_json(
            self.compile_url, {"source": VALID_MJML, "source_format": "mjml"}
        )
        self.assertEqual(response.status_code, 403)

    def test_compile_mjml_returns_html(self):
        self.client.force_login(self.admin)
        response = self._post_json(
            self.compile_url, {"source": VALID_MJML, "source_format": "mjml"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertIn("<table", data["html"])
        self.assertIsNone(data["error"])

    def test_compile_unknown_tag_reports_error(self):
        self.client.force_login(self.admin)
        source = VALID_MJML.replace(
            "</mj-text>", "</mj-text><mj-naoexiste>x</mj-naoexiste>"
        )
        response = self._post_json(
            self.compile_url, {"source": source, "source_format": "mjml"}
        )
        data = response.json()
        self.assertFalse(data["ok"])
        self.assertIn("mj-naoexiste", data["error"])

    def test_compile_html_format_echoes_source(self):
        self.client.force_login(self.admin)
        source = "<style>p{color:red}</style><p>Hello</p>"
        response = self._post_json(
            self.compile_url, {"source": source, "source_format": "html"}
        )
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["html"], source)

    def test_compile_broken_markup_reports_error(self):
        self.client.force_login(self.admin)
        response = self._post_json(
            self.compile_url,
            {"source": BROKEN_MJML, "source_format": "mjml"},
        )
        data = response.json()
        self.assertFalse(data["ok"])
        self.assertTrue(data["error"])

    def test_compile_invalid_json_returns_400(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            self.compile_url, data="{not json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_compile_requires_post(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.compile_url).status_code, 405)

    def test_compile_does_not_persist(self):
        self.client.force_login(self.admin)
        new_source = VALID_MJML.replace("Hello", "Changed")
        response = self._post_json(
            self.compile_url, {"source": new_source, "source_format": "mjml"}
        )
        self.assertTrue(response.json()["ok"])
        self.template.refresh_from_db()
        self.assertEqual(self.template.source, VALID_MJML)

    def test_save_persists_valid_source_and_body(self):
        self.client.force_login(self.admin)
        new_source = VALID_MJML.replace("Hello", "Saved")
        response = self._post_json(
            self.save_url, {"source": new_source, "source_format": "mjml"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])

        self.template.refresh_from_db()
        self.assertEqual(self.template.source, new_source)
        self.assertEqual(self.template.source_format, "mjml")
        self.assertIn("<table", self.template.body)
        self.assertIn("Saved", self.template.body)

    def test_save_refuses_invalid_source(self):
        self.client.force_login(self.admin)
        previous = {
            "source": self.template.source,
            "source_format": self.template.source_format,
            "body": self.template.body,
        }
        response = self._post_json(
            self.save_url, {"source": BROKEN_MJML, "source_format": "mjml"}
        )
        data = response.json()
        self.assertFalse(data["ok"])
        self.assertTrue(data["error"])

        self.template.refresh_from_db()
        self.assertEqual(self.template.source, previous["source"])
        self.assertEqual(self.template.source_format, previous["source_format"])
        self.assertEqual(self.template.body, previous["body"])

    def test_save_html_format_updates_body(self):
        self.client.force_login(self.admin)
        source = "<style>p{color:green}</style><p>Hello {{ name }}</p>"
        response = self._post_json(
            self.save_url, {"source": source, "source_format": "html"}
        )
        self.assertTrue(response.json()["ok"])
        self.template.refresh_from_db()
        self.assertEqual(self.template.source, source)
        self.assertEqual(self.template.source_format, "html")
        self.assertEqual(self.template.body, source)

    def test_save_requires_change_permission(self):
        self.client.force_login(self.staff)
        response = self._post_json(
            self.save_url, {"source": VALID_MJML, "source_format": "mjml"}
        )
        self.assertEqual(response.status_code, 403)
