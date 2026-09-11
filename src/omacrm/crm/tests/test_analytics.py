from datetime import date

from constance.test import override_config
from django.test import TestCase
from djmoney.money import Money

from omacrm.core.models import Role, User
from omacrm.crm.models import Account, Opportunity
from omacrm.crm.services.analytics import format_compact, sales_by_month

TODAY = date(2026, 9, 15)


class FormatCompactTests(TestCase):
    def test_compact_amounts(self):
        self.assertEqual(format_compact(0), "0")
        self.assertEqual(format_compact(950), "950")
        self.assertEqual(format_compact(1234), "1.2K")
        self.assertEqual(format_compact(97440), "97.4K")
        self.assertEqual(format_compact(120000), "120K")
        self.assertEqual(format_compact(2_500_000), "2.5M")
        self.assertEqual(format_compact(3_000_000_000), "3B")


class SalesByMonthTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "analytics", "analytics@example.com", "pw"
        )
        self.account = Account.objects.create(name="Analytics Co")

    def _opportunity(self, name, stage, close_date, **kwargs):
        converted = kwargs.pop("converted", 0)
        weighted = kwargs.pop("weighted", 0)
        opportunity = Opportunity.objects.create(
            name=name,
            stage=stage,
            close_date=close_date,
            account=self.account,
            amount=Money(kwargs.pop("amount", 1000), "USD"),
            **kwargs,
        )
        Opportunity.objects.filter(pk=opportunity.pk).update(
            amount_converted=converted,
            amount_weighted=weighted,
        )
        opportunity.refresh_from_db()
        return opportunity

    @override_config(base_currency="USD")
    def test_series_buckets_totals_and_exclusions(self):
        self._opportunity(
            "Won now", "Closed Won", TODAY, converted=1000, weighted=0
        )
        self._opportunity(
            "Won five months ago",
            "Closed Won",
            date(2026, 4, 10),
            converted=2000,
            weighted=0,
        )
        self._opportunity(
            "Lost now", "Closed Lost", TODAY, converted=999, weighted=0
        )
        self._opportunity(
            "Open now", "Negotiation", TODAY, converted=0, weighted=3000
        )
        self._opportunity(
            "Open without date", "Proposal", None, converted=0, weighted=888
        )

        sales = sales_by_month(self.admin, today=TODAY)

        self.assertEqual(len(sales["labels"]), 12)
        self.assertEqual(sales["labels"][-1], "Sep 2026")
        self.assertEqual(sales["labels"][0], "Oct 2025")
        self.assertEqual(sales["won"][-1], 1000)
        self.assertEqual(sales["won"][6], 2000)
        self.assertEqual(sum(sales["won"]), 3000)
        self.assertEqual(sales["weighted"][-1], 3000)
        self.assertEqual(sum(sales["weighted"]), 3000)
        self.assertEqual(sales["won_total"], 3000)
        self.assertEqual(sales["pipeline_total"], 3000)
        self.assertEqual(sales["won_display"], "3K")
        self.assertEqual(sales["pipeline_display"], "3K")
        self.assertEqual(sales["currency"], "USD")

    def test_months_without_data_are_zero_filled(self):
        self._opportunity(
            "Old won", "Closed Won", date(2025, 10, 5), converted=500, weighted=0
        )
        sales = sales_by_month(self.admin, today=TODAY)
        self.assertEqual(sales["won"][0], 500)
        self.assertEqual(sales["won"][5], 0)

    def test_acl_scopes_won_and_pipeline(self):
        role = Role.objects.create(
            name="Own opportunities", data={"Opportunity": {"read": "own"}}
        )
        staff = User.objects.create_user(
            "analytics-staff", "staff@example.com", "pw", is_staff=True
        )
        staff.roles.add(role)
        other = User.objects.create_user("other-sales", "other@example.com", "pw")

        self._opportunity(
            "Mine",
            "Closed Won",
            TODAY,
            converted=700,
            weighted=0,
            assigned_user=staff,
        )
        self._opportunity(
            "Theirs",
            "Closed Won",
            TODAY,
            converted=1300,
            weighted=0,
            assigned_user=other,
        )
        self._opportunity(
            "My open",
            "Proposal",
            TODAY,
            converted=0,
            weighted=400,
            assigned_user=staff,
        )

        sales = sales_by_month(staff, today=TODAY)
        self.assertEqual(sales["won_total"], 700)
        self.assertEqual(sales["pipeline_total"], 400)

    def test_acl_without_read_returns_zeros(self):
        self._opportunity(
            "Hidden", "Closed Won", TODAY, converted=1500, weighted=0
        )
        role = Role.objects.create(
            name="No opportunities", data={"Opportunity": {"read": "no"}}
        )
        staff = User.objects.create_user(
            "analytics-no", "no@example.com", "pw", is_staff=True
        )
        staff.roles.add(role)

        sales = sales_by_month(staff, today=TODAY)
        self.assertEqual(sales["won_total"], 0)
        self.assertEqual(sales["pipeline_total"], 0)
