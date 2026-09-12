from decimal import Decimal

from django.contrib import admin
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import translation
from djmoney.money import Money

from omacrm.core.metadata.registry import registry
from omacrm.core.models import CustomEntity, CustomField, DynamicRecord, User
from omacrm.core.services import custom_entities
from omacrm.core.services.formatting import format_compact, format_currency_compact
from omacrm.crm.models import Account, Campaign, Opportunity
from omacrm.crm.services import analytics


def _request(user):
    request = RequestFactory().get("/")
    request.user = user
    return request


class CurrencyColumnTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            "currency-admin", "currency@example.com", "pw"
        )
        self.client.force_login(self.admin_user)
        self.account = Account.objects.create(name="Money Co")
        self.model_admin = admin.site._registry[Opportunity]
        self.columns = self.model_admin.get_list_display(_request(self.admin_user))

    def _column(self, order_field):
        return next(
            column
            for column in self.columns
            if getattr(column, "admin_order_field", None) == order_field
        )

    def test_money_column_is_compact_with_symbol_and_full_title(self):
        opportunity = Opportunity.objects.create(
            name="Big deal", account=self.account, amount=Money(1200000, "BRL")
        )
        with translation.override("en-us"):
            cell = str(self._column("amount")(opportunity))
        self.assertHTMLEqual(cell, '<span title="R$1,200,000.00">R$ 1.2M</span>')

    def test_currency_value_without_money_has_no_symbol(self):
        campaign_admin = admin.site._registry[Campaign]
        field_def = registry.field("Campaign", "revenue")
        campaign = Campaign.objects.create(
            name="Fall campaign", revenue=Decimal("1200000")
        )
        campaign.refresh_from_db()
        with translation.override("en-us"):
            cell = str(campaign_admin._currency_display(field_def)(campaign))
        self.assertHTMLEqual(cell, '<span title="1200000.00">1.2M</span>')

    def test_empty_amount_is_not_zero(self):
        opportunity = Opportunity.objects.create(
            name="No amount", account=self.account
        )
        self.assertIsNone(self._column("amount")(opportunity))

    def test_non_currency_columns_are_untouched(self):
        self.assertIn("probability", self.columns)
        self.assertNotIn("amount", self.columns)
        self.assertIn("display_stage", self.columns)

    def test_currency_column_stays_sortable(self):
        for name, amount in (("High", 3_000_000), ("Low", 1_000), ("Mid", 500_000)):
            Opportunity.objects.create(
                name=name, account=self.account, amount=Money(amount, "USD")
            )
        self.assertEqual(self._column("amount").admin_order_field, "amount")
        url = reverse("admin:crm_opportunity_changelist")
        response = self.client.get(url)
        index = next(
            i
            for i, column in enumerate(response.context["cl"].list_display)
            if getattr(column, "admin_order_field", None) == "amount"
        )

        ascending = self.client.get(url, {"o": index})
        self.assertEqual(ascending.status_code, 200)
        self.assertEqual(
            [obj.name for obj in ascending.context["cl"].result_list],
            ["Low", "Mid", "High"],
        )

        descending = self.client.get(url, {"o": f"-{index}"})
        self.assertEqual(descending.status_code, 200)
        self.assertEqual(
            [obj.name for obj in descending.context["cl"].result_list],
            ["High", "Mid", "Low"],
        )

    def test_changelist_renders_compact_amount(self):
        opportunity = Opportunity.objects.create(
            name="Big deal", account=self.account, amount=Money(1200000, "BRL")
        )
        response = self.client.get(reverse("admin:crm_opportunity_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'title="{opportunity.amount}"')
        self.assertContains(response, "R$ 1.2M")


class CustomCurrencyColumnTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            "custom-currency", "custom-currency@example.com", "pw"
        )
        self.entity = CustomEntity.objects.create(name="Asset", label="Asset")
        self.addCleanup(registry.invalidate)
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        DynamicRecord.objects.filter(entity_type="Asset").delete()
        CustomField.objects.filter(entity_type="Asset").delete()
        custom_entities.unregister(self.entity)
        if self.entity.pk:
            self.entity.delete()
        registry.invalidate()

    def test_custom_currency_column_is_compact(self):
        CustomField.objects.create(
            entity_type="Asset",
            name="budget",
            label="Budget",
            field_type="currency",
        )
        registry.invalidate()
        proxy = custom_entities.get_proxy("Asset")
        record = proxy.objects.create(
            entity_type="Asset", name="HQ", custom_data={"budget": 1200000}
        )
        model_admin = admin.site._registry[proxy]
        columns = model_admin.get_list_display(_request(self.admin_user))
        budget = next(
            column
            for column in columns
            if getattr(column, "admin_order_field", None)
            == "custom_data__budget"
        )
        with translation.override("en-us"):
            cell = str(budget(record))
        self.assertHTMLEqual(cell, '<span title="1200000">1.2M</span>')


class FormatterTests(TestCase):
    def test_analytics_reexports_core_formatter(self):
        self.assertIs(analytics.format_compact, format_compact)

    def test_plain_number_has_no_currency_symbol(self):
        self.assertEqual(format_currency_compact(1200000), ("1.2M", "1200000"))

    def test_empty_values_return_none(self):
        self.assertIsNone(format_currency_compact(None))
        self.assertIsNone(format_currency_compact(""))
