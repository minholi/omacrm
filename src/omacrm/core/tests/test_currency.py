from decimal import Decimal

from django.test import TestCase

from omacrm.core.models import Currency
from omacrm.core.services.currency import base_currency, convert, get_rate


class CurrencyTests(TestCase):
    def test_base_currency(self):
        self.assertEqual(base_currency(), "USD")

    def test_convert_between_currencies(self):
        Currency.objects.create(code="EUR", rate=Decimal("0.9"))
        self.assertEqual(convert(100, "EUR", "USD"), Decimal("90.00"))
        self.assertEqual(convert(90, "USD", "EUR"), Decimal("100.00"))
        self.assertEqual(get_rate("EUR"), Decimal("0.9"))

    def test_unknown_currency_falls_back_to_one(self):
        self.assertEqual(convert(50, "XXX", "USD"), Decimal("50.00"))

    def test_convert_none(self):
        self.assertIsNone(convert(None, "EUR"))
