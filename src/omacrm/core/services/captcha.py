"""Captcha verification for public forms.

One switchable implementation covers Google reCAPTCHA v3 and Cloudflare
Turnstile: both verify a token by posting ``secret``/``response`` to a
siteverify endpoint and answering with ``success`` and optional ``action``
and ``score``. The provider, keys and threshold are constance settings, so an
install can pick either without code changes; ``captcha_verify_url`` overrides
the endpoint for self-hosted or compatible services (and for tests).
"""

import json
import logging
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

VERIFY_URLS = {
    "recaptcha": "https://www.google.com/recaptcha/api/siteverify",
    "turnstile": "https://challenges.cloudflare.com/turnstile/v0/siteverify",
}
DEFAULT_SCORE_THRESHOLD = 0.2
TIMEOUT = 10


def _setting(name: str, default):
    try:
        from constance import config
    except Exception:  # noqa: BLE001 - constance may be unavailable
        return default
    value = getattr(config, name, default)
    return default if value is None else value


def provider() -> str:
    """Return the configured provider key, or ``""`` when disabled/unknown."""

    value = str(_setting("captcha_provider", "") or "").strip().lower()
    return value if value in VERIFY_URLS else ""


def verify_url() -> str:
    override = str(_setting("captcha_verify_url", "") or "").strip()
    return override or VERIFY_URLS.get(provider(), "")


def site_key() -> str:
    return str(_setting("captcha_site_key", "") or "").strip()


def is_configured() -> bool:
    """Whether a provider and its secret key are set."""

    secret = str(_setting("captcha_secret_key", "") or "").strip()
    return bool(provider() and secret)


def verify(
    token: str, action: str = "lead_capture", remote_ip: str | None = None
) -> bool:
    """Verify one captcha token. Never raises; failures are logged."""

    provider_name = provider()
    secret = str(_setting("captcha_secret_key", "") or "").strip()
    if not provider_name or not secret:
        logger.error("Captcha verification requested but no provider is configured")
        return False

    token = (token or "").strip()
    if not token:
        return False

    payload = {"secret": secret, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip
    request = Request(
        verify_url(),
        data=urlencode(payload).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 - configured URL
            data = json.loads(response.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - network/parse failures fail verification
        logger.exception("Captcha verification request failed")
        return False

    if not isinstance(data, dict) or not data.get("success"):
        logger.warning(
            "Captcha verification rejected: %s",
            data.get("error-codes", data) if isinstance(data, dict) else data,
        )
        return False

    result_action = data.get("action")
    if result_action is not None and action and str(result_action) != action:
        logger.warning(
            "Captcha action mismatch: expected %s, got %s", action, result_action
        )
        return False

    score = data.get("score")
    if score is None:
        if provider_name == "recaptcha":
            logger.warning("Captcha response for reCAPTCHA without a score")
            return False
        return True

    try:
        threshold = float(_setting("captcha_score_threshold", DEFAULT_SCORE_THRESHOLD))
    except (TypeError, ValueError):
        threshold = DEFAULT_SCORE_THRESHOLD
    if not isinstance(score, (int, float)) or float(score) < threshold:
        logger.warning("Captcha score %s below threshold %s", score, threshold)
        return False
    return True
