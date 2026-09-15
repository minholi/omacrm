"""Application secrets: named credentials stored encrypted at rest."""

import logging

from omacrm.core.models import AppSecret

logger = logging.getLogger(__name__)


def get(name: str) -> str:
    """Return the plain value of a secret, or ``""`` when unavailable."""

    secret = AppSecret.objects.filter(name=name).first()
    if secret is None:
        return ""
    return secret.get_value()


def set(name: str, value: str, description: str = "") -> AppSecret:
    """Create or update a secret and store its value encrypted."""

    secret = AppSecret.objects.filter(name=name).first()
    if secret is None:
        secret = AppSecret(name=name)
    secret.set_value(value)
    secret.description = description
    secret.save()
    return secret


def names() -> list[str]:
    return list(AppSecret.objects.order_by("name").values_list("name", flat=True))
