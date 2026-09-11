import json
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from constance.test import override_config
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from omacrm.core.models import Currency, CurrencyRate, User
from omacrm.core.services.builtin_jobs import sync_currency_rates
from omacrm.core.services.currency import (
    base_currency,
    convert,
    get_rate,
    set_rate,
)
from omacrm.crm.models import Opportunity


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


class HistoricalRateTests(TestCase):
    def setUp(self):
        self.eur = Currency.objects.create(code="EUR", rate=Decimal("0.9"))
        CurrencyRate.objects.create(
            currency=self.eur, date=date(2026, 1, 1), rate=Decimal("0.8")
        )
        CurrencyRate.objects.create(
            currency=self.eur, date=date(2026, 6, 1), rate=Decimal("0.95")
        )

    def test_get_rate_uses_effective_date(self):
        self.assertEqual(get_rate("EUR", date=date(2026, 1, 1)), Decimal("0.8"))
        self.assertEqual(get_rate("EUR", date=date(2026, 3, 1)), Decimal("0.8"))
        self.assertEqual(get_rate("EUR", date=date(2026, 6, 15)), Decimal("0.95"))

    def test_get_rate_falls_back_without_history(self):
        self.assertEqual(get_rate("EUR", date=date(2025, 1, 1)), Decimal("0.9"))
        self.assertEqual(get_rate("EUR"), Decimal("0.9"))

    def test_convert_with_date(self):
        self.assertEqual(
            convert(100, "EUR", "USD", date=date(2026, 3, 1)), Decimal("80.00")
        )
        self.assertEqual(convert(100, "EUR", "USD"), Decimal("90.00"))

    def test_base_currency_ignores_history(self):
        CurrencyRate.objects.create(
            currency=Currency.objects.create(code="USD"),
            date=date(2026, 3, 1),
            rate=Decimal("7"),
        )
        self.assertEqual(get_rate("USD", date=date(2026, 3, 1)), Decimal("1"))

    def test_set_rate_upserts(self):
        set_rate("EUR", "0.99", date=date(2026, 7, 1))
        self.assertEqual(get_rate("EUR", date=date(2026, 7, 1)), Decimal("0.99"))
        set_rate("EUR", Decimal("0.97"), date=date(2026, 7, 1))
        self.assertEqual(
            CurrencyRate.objects.filter(
                currency=self.eur, date=date(2026, 7, 1)
            ).count(),
            1,
        )
        self.assertEqual(get_rate("EUR", date=date(2026, 7, 1)), Decimal("0.97"))

    def test_opportunity_conversion_uses_close_date(self):
        opportunity = Opportunity.objects.create(
            name="Euro Deal",
            amount=Money(100, "EUR"),
            close_date=date(2026, 3, 1),
        )
        opportunity.refresh_from_db()
        self.assertEqual(opportunity.amount_converted, Decimal("80.00"))


class SyncCurrencyRatesTests(TestCase):
    def setUp(self):
        Currency.objects.create(code="EUR", rate=Decimal("1"))

    def _response(self, payload):
        response = MagicMock()
        response.read.return_value = json.dumps(payload).encode()
        response.__enter__ = MagicMock(return_value=response)
        response.__exit__ = MagicMock(return_value=False)
        return response

    @override_config(
        currency_rates_url="https://rates.example/api", base_currency="USD"
    )
    def test_sync_updates_rates_and_currency(self):
        payload = {"base": "USD", "rates": {"EUR": 0.92, "XXX": 5, "USD": 1}}
        with patch(
            "omacrm.core.services.builtin_jobs.urlopen",
            return_value=self._response(payload),
        ):
            updated = sync_currency_rates(None)

        self.assertEqual(updated, 1)
        eur = Currency.objects.get(code="EUR")
        self.assertEqual(eur.rate, Decimal("0.92"))
        row = CurrencyRate.objects.get(currency=eur)
        self.assertEqual(row.date, timezone.localdate())
        self.assertEqual(row.rate, Decimal("0.92"))

    @override_config(currency_rates_url="")
    def test_sync_disabled_without_url(self):
        self.assertEqual(sync_currency_rates(None), 0)

    @override_config(currency_rates_url="https://rates.example/api")
    def test_sync_failure_returns_zero(self):
        with patch(
            "omacrm.core.services.builtin_jobs.urlopen", side_effect=OSError("down")
        ):
            self.assertEqual(sync_currency_rates(None), 0)

    @override_config(
        currency_rates_url="https://rates.example/api", base_currency="USD"
    )
    def test_sync_skips_mismatched_base(self):
        payload = {"base": "EUR", "rates": {"EUR": 1.0}}
        with patch(
            "omacrm.core.services.builtin_jobs.urlopen",
            return_value=self._response(payload),
        ):
            self.assertEqual(sync_currency_rates(None), 0)


class CurrencyAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("rates-admin", "ra@example.com", "pw")
        self.client.force_login(self.admin)

    def test_currency_and_rate_admin_pages_render(self):
        currency = Currency.objects.create(code="EUR", rate=Decimal("0.9"))
        CurrencyRate.objects.create(
            currency=currency, date=date(2026, 1, 1), rate=Decimal("0.8")
        )
        for url in (
            "/admin/core/currency/",
            f"/admin/core/currency/{currency.pk}/change/",
            "/admin/core/currencyrate/",
        ):
            self.assertEqual(self.client.get(url).status_code, 200, url)
