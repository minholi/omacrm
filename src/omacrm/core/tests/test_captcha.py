import json
from unittest.mock import MagicMock, patch

from constance.test import override_config
from django.test import TestCase

from omacrm.core.services import captcha

RECAPTCHA_OK = {"success": True, "action": "lead_capture", "score": 0.7}


def _response(payload):
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode()
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    return response


class CaptchaConfigTests(TestCase):
    @override_config(captcha_provider="", captcha_secret_key="")
    def test_disabled_by_default(self):
        self.assertEqual(captcha.provider(), "")
        self.assertFalse(captcha.is_configured())

    @override_config(captcha_provider=" Recaptcha ", captcha_secret_key="secret")
    def test_provider_is_normalized(self):
        self.assertEqual(captcha.provider(), "recaptcha")
        self.assertTrue(captcha.is_configured())

    @override_config(captcha_provider="nope", captcha_secret_key="secret")
    def test_unknown_provider_is_treated_as_disabled(self):
        self.assertEqual(captcha.provider(), "")
        self.assertFalse(captcha.is_configured())

    @override_config(captcha_provider="recaptcha", captcha_secret_key="  ")
    def test_secret_is_required(self):
        self.assertFalse(captcha.is_configured())

    @override_config(captcha_provider="recaptcha", captcha_verify_url="")
    def test_default_verify_url_per_provider(self):
        self.assertEqual(
            captcha.verify_url(), "https://www.google.com/recaptcha/api/siteverify"
        )

    @override_config(
        captcha_provider="turnstile",
        captcha_verify_url="https://captcha.example/verify",
    )
    def test_verify_url_override(self):
        self.assertEqual(captcha.verify_url(), "https://captcha.example/verify")


class CaptchaVerifyTests(TestCase):
    @override_config(captcha_provider="recaptcha", captcha_secret_key="secret")
    def test_success_posts_secret_and_token(self):
        with patch(
            "omacrm.core.services.captcha.urlopen",
            return_value=_response(RECAPTCHA_OK),
        ) as mocked:
            self.assertTrue(captcha.verify("token", remote_ip="10.0.0.1"))

        request = mocked.call_args.args[0]
        self.assertEqual(request.full_url, captcha.verify_url())
        self.assertIn(b"secret=secret", request.data)
        self.assertIn(b"response=token", request.data)
        self.assertIn(b"remoteip=10.0.0.1", request.data)
        self.assertEqual(mocked.call_args.kwargs["timeout"], captcha.TIMEOUT)

    @override_config(captcha_provider="recaptcha", captcha_secret_key="secret")
    def test_missing_token_skips_the_request(self):
        with patch("omacrm.core.services.captcha.urlopen") as mocked:
            self.assertFalse(captcha.verify(""))
        mocked.assert_not_called()

    @override_config(captcha_provider="", captcha_secret_key="")
    def test_unconfigured_provider_fails(self):
        with patch("omacrm.core.services.captcha.urlopen") as mocked:
            self.assertFalse(captcha.verify("token"))
        mocked.assert_not_called()

    @override_config(captcha_provider="recaptcha", captcha_secret_key="secret")
    def test_failed_response_is_rejected(self):
        payload = {"success": False, "error-codes": ["invalid-input-response"]}
        with patch(
            "omacrm.core.services.captcha.urlopen", return_value=_response(payload)
        ):
            self.assertFalse(captcha.verify("token"))

    @override_config(captcha_provider="recaptcha", captcha_secret_key="secret")
    def test_action_mismatch_is_rejected(self):
        payload = dict(RECAPTCHA_OK, action="login")
        with patch(
            "omacrm.core.services.captcha.urlopen", return_value=_response(payload)
        ):
            self.assertFalse(captcha.verify("token", action="lead_capture"))

    @override_config(captcha_provider="recaptcha", captcha_secret_key="secret")
    def test_low_score_is_rejected(self):
        payload = dict(RECAPTCHA_OK, score=0.1)
        with patch(
            "omacrm.core.services.captcha.urlopen", return_value=_response(payload)
        ):
            self.assertFalse(captcha.verify("token"))

    @override_config(
        captcha_provider="recaptcha",
        captcha_secret_key="secret",
        captcha_score_threshold=0.9,
    )
    def test_threshold_is_configurable(self):
        payload = dict(RECAPTCHA_OK, score=0.7)
        with patch(
            "omacrm.core.services.captcha.urlopen", return_value=_response(payload)
        ):
            self.assertFalse(captcha.verify("token"))

    @override_config(captcha_provider="recaptcha", captcha_secret_key="secret")
    def test_recaptcha_response_without_score_is_rejected(self):
        payload = {"success": True, "action": "lead_capture"}
        with patch(
            "omacrm.core.services.captcha.urlopen", return_value=_response(payload)
        ):
            self.assertFalse(captcha.verify("token"))

    @override_config(captcha_provider="turnstile", captcha_secret_key="secret")
    def test_turnstile_response_without_score_is_accepted(self):
        payload = {"success": True}
        with patch(
            "omacrm.core.services.captcha.urlopen", return_value=_response(payload)
        ):
            self.assertTrue(captcha.verify("token"))

    @override_config(captcha_provider="turnstile", captcha_secret_key="secret")
    def test_optional_action_is_checked_when_returned(self):
        payload = {"success": True, "action": "other"}
        with patch(
            "omacrm.core.services.captcha.urlopen", return_value=_response(payload)
        ):
            self.assertFalse(captcha.verify("token", action="lead_capture"))

    @override_config(captcha_provider="recaptcha", captcha_secret_key="secret")
    def test_network_failure_fails_verification(self):
        with patch(
            "omacrm.core.services.captcha.urlopen", side_effect=OSError("down")
        ):
            self.assertFalse(captcha.verify("token"))

    @override_config(captcha_provider="recaptcha", captcha_secret_key="secret")
    def test_malformed_response_fails_verification(self):
        response = MagicMock()
        response.read.return_value = b"not json"
        response.__enter__ = MagicMock(return_value=response)
        response.__exit__ = MagicMock(return_value=False)
        with patch("omacrm.core.services.captcha.urlopen", return_value=response):
            self.assertFalse(captcha.verify("token"))
