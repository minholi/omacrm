from decimal import Decimal

from django.db import OperationalError, ProgrammingError


def base_currency() -> str:
    try:
        from constance import config

        value = getattr(config, "base_currency", None)
    except Exception:  # noqa: BLE001 - constance may be unavailable during setup
        value = None
    return value or "USD"


def _stored_rate(code: str) -> Decimal:
    from omacrm.core.models import Currency

    try:
        row = Currency.objects.filter(code=code, is_active=True).first()
    except (OperationalError, ProgrammingError):
        row = None
    return row.rate if row else Decimal("1")


def get_rate(code: str | None, date=None) -> Decimal:
    """Return the value of one unit of ``code`` in the base currency.

    When ``date`` is given, the most recent :class:`CurrencyRate` on or before
    that date wins; otherwise the current ``Currency.rate`` is used.
    """

    if not code:
        return Decimal("1")
    if code == base_currency():
        return Decimal("1")

    if date is not None:
        from omacrm.core.models import CurrencyRate

        try:
            row = (
                CurrencyRate.objects.filter(currency__code=code, date__lte=date)
                .order_by("-date")
                .first()
            )
        except (OperationalError, ProgrammingError):
            row = None
        if row is not None:
            return row.rate

    return _stored_rate(code)


def convert(amount, from_code: str | None, to_code: str | None = None, date=None):
    """Convert a decimal amount between currencies using stored rates."""

    if amount is None:
        return None
    to_code = to_code or base_currency()
    from_rate = get_rate(from_code or to_code, date=date)
    to_rate = get_rate(to_code, date=date)
    if not to_rate:
        to_rate = Decimal("1")
    value = Decimal(amount) * from_rate / to_rate
    return value.quantize(Decimal("0.01"))


def set_rate(code: str, rate, date=None):
    """Create or update the dated rate of ``code`` and return the row."""

    from django.utils import timezone

    from omacrm.core.models import Currency, CurrencyRate

    date = date or timezone.localdate()
    currency, _created = Currency.objects.get_or_create(code=code)
    row, _created = CurrencyRate.objects.update_or_create(
        currency=currency,
        date=date,
        defaults={"rate": Decimal(str(rate))},
    )
    return row
