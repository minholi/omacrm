import json
from unittest.mock import MagicMock, patch

from constance.test import override_config
from django.test import TestCase
from django.urls import reverse

from omacrm.crm.models import Lead, LeadCapture

RECAPTCHA_OK = {"success": True, "action": "lead_capture", "score": 0.7}

CONFIGURED = {
    "captcha_provider": "recaptcha",
    "captcha_secret_key": "secret",
}


def _response(payload):
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode()
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    return response


@override_config(**CONFIGURED)
class LeadCaptureCaptchaTests(TestCase):
    def setUp(self):
        self.capture = LeadCapture.objects.create(
            name="Guarded form", form_captcha=True
        )

    def _post(self, extra=None):
        payload = {
            "first_name": "Web",
            "last_name": "Visitor",
            "email_address": "web@example.com",
        }
        payload.update(extra or {})
        return self.client.post(
            reverse("lead_capture", args=[self.capture.api_key]),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def _leads(self):
        return Lead.objects.filter(email_address="web@example.com")

    def test_missing_token_is_rejected(self):
        with patch("omacrm.core.services.captcha.urlopen") as mocked:
            response = self._post()
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self._leads().exists())
        mocked.assert_not_called()

    def test_failed_verification_is_rejected(self):
        payload = {"success": False, "error-codes": ["invalid-input-response"]}
        with patch(
            "omacrm.core.services.captcha.urlopen", return_value=_response(payload)
        ):
            response = self._post({"captcha_token": "token"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self._leads().exists())

    def test_low_score_is_rejected(self):
        payload = dict(RECAPTCHA_OK, score=0.1)
        with patch(
            "omacrm.core.services.captcha.urlopen", return_value=_response(payload)
        ):
            response = self._post({"captcha_token": "token"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self._leads().exists())

    def test_action_mismatch_is_rejected(self):
        payload = dict(RECAPTCHA_OK, action="login")
        with patch(
            "omacrm.core.services.captcha.urlopen", return_value=_response(payload)
        ):
            response = self._post({"captcha_token": "token"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self._leads().exists())

    def test_valid_token_creates_the_lead(self):
        with patch(
            "omacrm.core.services.captcha.urlopen",
            return_value=_response(RECAPTCHA_OK),
        ) as mocked:
            response = self._post({"captcha_token": "token"})
        self.assertEqual(response.status_code, 201)
        lead = self._leads().get()
        self.assertEqual(lead.source, "Web Site")
        request = mocked.call_args.args[0]
        self.assertIn(b"remoteip=127.0.0.1", request.data)

    def test_browser_token_field_is_accepted(self):
        with patch(
            "omacrm.core.services.captcha.urlopen",
            return_value=_response(RECAPTCHA_OK),
        ):
            response = self._post({"g-recaptcha-response": "token"})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(self._leads().exists())

    def test_turnstile_without_score_is_accepted(self):
        with override_config(captcha_provider="turnstile"):
            with patch(
                "omacrm.core.services.captcha.urlopen",
                return_value=_response({"success": True}),
            ):
                response = self._post({"cf-turnstile-response": "token"})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(self._leads().exists())

    def test_unconfigured_provider_fails_closed(self):
        with override_config(captcha_provider="", captcha_secret_key=""):
            response = self._post({"captcha_token": "token"})
        self.assertEqual(response.status_code, 503)
        self.assertFalse(self._leads().exists())

    def test_disabled_capture_ignores_captcha(self):
        self.capture.form_captcha = False
        self.capture.save(update_fields=["form_captcha"])
        with patch("omacrm.core.services.captcha.urlopen") as mocked:
            response = self._post()
        self.assertEqual(response.status_code, 201)
        self.assertTrue(self._leads().exists())
        mocked.assert_not_called()
