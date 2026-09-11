from decimal import Decimal

from django.db import OperationalError, ProgrammingError


def base_currency() -> str:
    try:
        from constance import config

        value = getattr(config, "base_currency", None)
    except Exception:  # noqa: BLE001 - constance may be unavailable during setup
        value = None
    return value or "USD"


def get_rate(code: str | None) -> Decimal:
    """Return the value of one unit of ``code`` in the base currency."""

    if not code:
        return Decimal("1")
    if code == base_currency():
        return Decimal("1")

    from omacrm.core.models import Currency

    try:
        row = Currency.objects.filter(code=code, is_active=True).first()
    except (OperationalError, ProgrammingError):
        row = None
    return row.rate if row else Decimal("1")


def convert(amount, from_code: str | None, to_code: str | None = None):
    """Convert a decimal amount between currencies using stored rates."""

    if amount is None:
        return None
    to_code = to_code or base_currency()
    from_rate = get_rate(from_code or to_code)
    to_rate = get_rate(to_code)
    if not to_rate:
        to_rate = Decimal("1")
    value = Decimal(amount) * from_rate / to_rate
    return value.quantize(Decimal("0.01"))
