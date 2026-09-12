"""Compact number and currency formatting shared by dashboard and admin."""

from babel.numbers import get_currency_symbol
from django.utils.formats import number_format
from djmoney.money import get_current_locale


def format_compact(value):
    """Compact amount for dashboard labels: 97440 -> 97.4K, 1200000 -> 1.2M."""

    number = float(value or 0)
    for threshold, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if abs(number) >= threshold:
            scaled = number_format(number / threshold, decimal_pos=1)
            return f"{scaled.rstrip('0').rstrip('.')}{suffix}"
    return number_format(number, decimal_pos=0, force_grouping=True)


def format_currency_compact(value):
    """Return ``(compact, exact)`` for a monetary value, or ``None`` if empty.

    django-money values keep the symbol of their currency; plain numbers
    (e.g. custom currency fields) are compacted on their own.
    """

    if value is None or value == "":
        return None
    if hasattr(value, "amount") and hasattr(value, "currency"):
        symbol = get_currency_symbol(value.currency.code, locale=get_current_locale())
        return f"{symbol} {format_compact(value.amount)}", str(value)
    return format_compact(value), str(value)
