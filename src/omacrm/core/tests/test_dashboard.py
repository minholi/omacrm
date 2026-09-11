import json
from datetime import date

from django.test import TestCase
from django.urls import reverse
from djmoney.money import Money

from omacrm.core.models import Role, User
from omacrm.crm.models import Account, Opportunity


class DashboardChartTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("dash", "dash@example.com", "pw")

    def test_dashboard_renders_sales_chart(self):
        account = Account.objects.create(name="Chart Co")
        opportunity = Opportunity.objects.create(
            name="Won deal",
            stage="Closed Won",
            close_date=date.today(),
            account=account,
            amount=Money(1234, "USD"),
        )
        Opportunity.objects.filter(pk=opportunity.pk).update(amount_converted=1234)

        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-type="bar"')

        chart = json.loads(response.context["sales_chart"])
        self.assertEqual(len(chart["labels"]), 12)
        self.assertEqual(
            [dataset["type"] for dataset in chart["datasets"]], ["bar", "line"]
        )
        self.assertEqual(chart["datasets"][0]["data"][-1], 1234)
        self.assertEqual(response.context["sales_totals"]["won"], 1234)
        self.assertEqual(response.context["sales_totals"]["won_display"], "1.2K")

    def test_dashboard_kpis_are_acl_scoped(self):
        role = Role.objects.create(
            name="Own accounts", data={"Account": {"read": "own"}}
        )
        staff = User.objects.create_user(
            "dash-staff", "dash-staff@example.com", "pw", is_staff=True
        )
        staff.roles.add(role)
        Account.objects.create(name="Mine", assigned_user=staff)
        Account.objects.create(name="Theirs", assigned_user=self.admin)

        self.client.force_login(staff)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        kpis = {str(kpi["label"]): kpi["value"] for kpi in response.context["kpis"]}
        self.assertEqual(kpis["Accounts"], 1)

        chart = json.loads(response.context["sales_chart"])
        self.assertEqual(chart["datasets"][0]["data"], [0.0] * 12)
