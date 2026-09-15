import json
from unittest.mock import MagicMock, patch

from constance.test import override_config
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from omacrm.core.models import User
from omacrm.crm.models import (
    Campaign,
    CampaignLogRecord,
    EmailTemplate,
    Lead,
    LeadCapture,
    TargetList,
    TargetListMember,
)

TURNSTILE_CONFIG = {
    "captcha_provider": "turnstile",
    "captcha_site_key": "1x00000000000000000000AA",
    "captcha_secret_key": "1x0000000000000000000000000000000AA",
}


def _response(payload):
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode()
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    return response


class LeadCaptureFormTests(TestCase):
    def setUp(self):
        self.capture = LeadCapture.objects.create(name="Website form")
        self.url = reverse("lead_capture_form", args=[self.capture.api_key])

    def _post(self, data):
        return self.client.post(self.url, data=data)

    def test_get_renders_default_fields(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        for label in ("First name", "Last name", "Email address", "Phone number"):
            self.assertContains(response, label)
        self.assertContains(response, self.capture.name)

    def test_get_honours_the_field_list(self):
        self.capture.field_list = ["first_name", "email_address", "nope"]
        self.capture.save(update_fields=["field_list"])
        response = self.client.get(self.url)
        self.assertContains(response, "First name")
        self.assertContains(response, "Email address")
        self.assertNotContains(response, "Last name")
        self.assertNotContains(response, "Phone number")

    def test_unknown_key_is_404(self):
        response = self.client.get(
            reverse("lead_capture_form", args=["nope"])
        )
        self.assertEqual(response.status_code, 404)

    def test_inactive_capture_is_404(self):
        self.capture.is_active = False
        self.capture.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_admin_links_to_the_public_form(self):
        admin = User.objects.create_superuser("form-admin", "form@example.com", "pw")
        self.client.force_login(admin)
        response = self.client.get(
            reverse("admin:crm_leadcapture_change", args=[self.capture.pk])
        )
        self.assertContains(response, self.url)

    def test_post_creates_lead_and_runs_capture_actions(self):
        target_list = TargetList.objects.create(name="Web leads")
        campaign = Campaign.objects.create(name="Web campaign")
        self.capture.target_list = target_list
        self.capture.campaign = campaign
        self.capture.source = "Web Site"
        self.capture.save()
        response = self._post(
            {
                "first_name": "Web",
                "last_name": "Visitor",
                "email_address": "web@example.com",
                "description": "Interested",
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Thank you")
        lead = Lead.objects.get(email_address="web@example.com")
        self.assertEqual(lead.source, "Web Site")
        self.assertEqual(lead.name, "Web Visitor")
        self.assertTrue(
            TargetListMember.objects.filter(
                target_list=target_list, entity_id=lead.pk
            ).exists()
        )
        self.assertTrue(
            CampaignLogRecord.objects.filter(
                campaign=campaign, action=CampaignLogRecord.Action.LEAD_CREATED
            ).exists()
        )

    def test_post_without_contact_info_is_rejected(self):
        response = self._post({"first_name": "Only"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "last name or an email address")
        self.assertFalse(Lead.objects.exists())

    def test_unknown_field_value_is_ignored(self):
        response = self._post(
            {
                "last_name": "Visitor",
                "email_address": "web@example.com",
                "status": "Converted",
            }
        )
        self.assertEqual(response.status_code, 200)
        lead = Lead.objects.get(email_address="web@example.com")
        self.assertEqual(lead.status, Lead.Status.NEW)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_opt_in_capture_defers_target_list(self):
        target_list = TargetList.objects.create(name="Opt-in leads")
        self.capture.target_list = target_list
        self.capture.opt_in_confirmation = True
        self.capture.opt_in_template = EmailTemplate.objects.create(
            name="Confirm",
            subject="Confirm",
            source="<p>Please confirm</p>",
            source_format="html",
        )
        self.capture.save()
        response = self._post(
            {"last_name": "In", "email_address": "optin@example.com"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "check your inbox")
        lead = Lead.objects.get(email_address="optin@example.com")
        self.assertFalse(lead.opt_in_confirmed)
        self.assertFalse(
            TargetListMember.objects.filter(
                target_list=target_list, entity_id=lead.pk
            ).exists()
        )
        self.assertEqual(len(mail.outbox), 1)

    @override_config(**TURNSTILE_CONFIG)
    def test_captcha_widget_is_rendered_when_enabled(self):
        self.capture.form_captcha = True
        self.capture.save(update_fields=["form_captcha"])
        response = self.client.get(self.url)
        self.assertContains(response, "cf-turnstile")
        self.assertContains(response, TURNSTILE_CONFIG["captcha_site_key"])
        self.assertContains(response, "challenges.cloudflare.com")

    @override_config(**TURNSTILE_CONFIG)
    def test_recaptcha_widget_is_rendered_when_selected(self):
        with override_config(
            captcha_provider="recaptcha",
            captcha_site_key="recaptcha-site-key",
        ):
            self.capture.form_captcha = True
            self.capture.save(update_fields=["form_captcha"])
            response = self.client.get(self.url)
        self.assertContains(response, "recaptcha/api.js")
        self.assertContains(response, "grecaptcha.execute")
        self.assertContains(response, "recaptcha-site-key")

    @override_config(**TURNSTILE_CONFIG)
    def test_captcha_blocks_submission_without_token(self):
        self.capture.form_captcha = True
        self.capture.save(update_fields=["form_captcha"])
        with patch("omacrm.core.services.captcha.urlopen") as mocked:
            response = self._post(
                {"last_name": "Visitor", "email_address": "web@example.com"}
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "complete the captcha")
        self.assertFalse(Lead.objects.exists())
        mocked.assert_not_called()

    @override_config(**TURNSTILE_CONFIG)
    def test_captcha_failure_blocks_submission(self):
        self.capture.form_captcha = True
        self.capture.save(update_fields=["form_captcha"])
        with patch(
            "omacrm.core.services.captcha.urlopen",
            return_value=_response({"success": False}),
        ):
            response = self._post(
                {
                    "last_name": "Visitor",
                    "email_address": "web@example.com",
                    "cf-turnstile-response": "token",
                }
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "captcha verification failed")
        self.assertFalse(Lead.objects.exists())

    @override_config(**TURNSTILE_CONFIG)
    def test_captcha_success_creates_lead(self):
        self.capture.form_captcha = True
        self.capture.save(update_fields=["form_captcha"])
        with patch(
            "omacrm.core.services.captcha.urlopen",
            return_value=_response({"success": True}),
        ):
            response = self._post(
                {
                    "last_name": "Visitor",
                    "email_address": "web@example.com",
                    "cf-turnstile-response": "token",
                }
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Thank you")
        self.assertTrue(Lead.objects.filter(email_address="web@example.com").exists())

    def test_captcha_required_without_provider_fails_closed(self):
        self.capture.form_captcha = True
        self.capture.save(update_fields=["form_captcha"])
        with override_config(captcha_provider="", captcha_secret_key=""):
            response = self._post(
                {"last_name": "Visitor", "email_address": "web@example.com"}
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "temporarily unavailable")
        self.assertFalse(Lead.objects.exists())

    @override_config(**TURNSTILE_CONFIG)
    def test_captcha_disabled_capture_ignores_the_provider(self):
        with patch("omacrm.core.services.captcha.urlopen") as mocked:
            response = self._post(
                {"last_name": "Visitor", "email_address": "web@example.com"}
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Lead.objects.filter(email_address="web@example.com").exists())
        mocked.assert_not_called()
