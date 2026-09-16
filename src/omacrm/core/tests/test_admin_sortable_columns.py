"""Rendered changelist sort links for metadata-driven columns.

``MetadataModelAdmin.get_list_display`` generates fresh closures for custom,
currency and star columns. Django builds the changelist columns and the
``cl.sortable_by`` fallback from two separate calls to it and matches them by
identity, so a fresh list per call silently made every generated column
unsortable. These tests assert the sort links from the rendered page, not from
admin internals.
"""

import re

from django.contrib import admin
from django.test import RequestFactory, TestCase
from django.urls import reverse
from djmoney.money import Money

from omacrm.core.metadata.registry import registry
from omacrm.core.models import CustomField, User
from omacrm.crm.models import Account, Opportunity, TargetList


def _request(user):
    request = RequestFactory().get("/")
    request.user = user
    return request


def _header_cells(response):
    html = response.content.decode()
    match = re.search(r"<thead.*?</thead>", html, re.S)
    if match is None:
        raise AssertionError("response has no <thead>")
    return re.findall(r"<th\b.*?</th>", match.group(0), re.S)


def _header_text(cell):
    return " ".join(re.sub(r"<[^>]+>", " ", cell).split())


def _header_label(cell):
    """The primary link text when sortable, the full cell text otherwise."""

    match = re.search(r"<a[^>]*>(.*?)</a>", cell, re.S)
    text = match.group(1) if match else cell
    return " ".join(re.sub(r"<[^>]+>", " ", text).split())


def _column_header(response, label):
    for cell in _header_cells(response):
        if _header_label(cell) == label:
            return cell
    raise AssertionError(f"no column header labelled {label!r}")


def _sort_url(cell):
    match = re.search(r'href="([^"]*[?&]o=-?\d+(?:\.\d+)*)"', cell)
    return match.group(1) if match else None


def _descending_sort_url(response, label):
    for href in re.findall(r'href="([^"]+)"', _column_header(response, label)):
        if re.search(r"[?&]o=-\d", href):
            return href
    raise AssertionError(f"no descending sort link for {label!r}")


def _result_names(response):
    return [obj.name for obj in response.context["cl"].result_list]


class ListDisplayIdentityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            "sort-admin", "sort-admin@example.com", "pw"
        )
        self.model_admin = admin.site._registry[Opportunity]

    def test_repeated_calls_return_the_same_instances(self):
        request = _request(self.user)
        first = self.model_admin.get_list_display(request)
        second = self.model_admin.get_list_display(request)
        self.assertIs(first, second)
        for left, right in zip(first, second):
            self.assertIs(left, right)

    def test_generated_columns_are_in_sortable_by(self):
        request = _request(self.user)
        columns = self.model_admin.get_list_display(request)
        sortable = self.model_admin.get_sortable_by(request)
        for column in columns:
            self.assertIn(column, sortable)

    def test_requests_do_not_share_generated_columns(self):
        first = self.model_admin.get_list_display(_request(self.user))
        second = self.model_admin.get_list_display(_request(self.user))
        self.assertIsNot(first, second)

        def amount_column(columns):
            return next(
                column
                for column in columns
                if getattr(column, "admin_order_field", None) == "amount"
            )

        self.assertIsNot(amount_column(first), amount_column(second))


class RenderedCurrencyColumnTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            "sort-currency", "sort-currency@example.com", "pw"
        )
        self.client.force_login(self.user)
        self.account = Account.objects.create(name="Money Co")
        for name, amount in (("High", 3_000_000), ("Low", 1_000), ("Mid", 500_000)):
            Opportunity.objects.create(
                name=name, account=self.account, amount=Money(amount, "USD")
            )

    def test_amount_header_link_sorts_both_ways(self):
        url = reverse("admin:crm_opportunity_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        sort_url = _sort_url(_column_header(response, "Amount"))
        self.assertIsNotNone(sort_url)

        ascending = self.client.get(url + sort_url)
        self.assertEqual(ascending.status_code, 200)
        self.assertEqual(_result_names(ascending), ["Low", "Mid", "High"])

        descending = self.client.get(url + _descending_sort_url(ascending, "Amount"))
        self.assertEqual(descending.status_code, 200)
        self.assertEqual(_result_names(descending), ["High", "Mid", "Low"])


class RenderedCustomFieldColumnTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            "sort-custom", "sort-custom@example.com", "pw"
        )
        self.client.force_login(self.user)
        self.addCleanup(registry.invalidate)
        CustomField.objects.create(
            entity_type="Account",
            name="is_strategic",
            label="Strategic Account",
            field_type="bool",
        )
        CustomField.objects.create(
            entity_type="Account", name="tier", label="Tier", field_type="enum"
        )
        registry.invalidate()

    def test_custom_field_headers_have_sort_links(self):
        Account.objects.create(name="Plain")
        response = self.client.get(reverse("admin:crm_account_changelist"))
        self.assertEqual(response.status_code, 200)
        for label in ("Strategic Account", "Tier"):
            self.assertIsNotNone(_sort_url(_column_header(response, label)), label)

    def test_strategic_account_header_link_sorts(self):
        Account.objects.create(name="Plain")
        Account.objects.create(name="Important", custom_data={"is_strategic": True})
        url = reverse("admin:crm_account_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        ascending = self.client.get(
            url + _sort_url(_column_header(response, "Strategic Account"))
        )
        self.assertEqual(ascending.status_code, 200)
        self.assertEqual(_result_names(ascending), ["Plain", "Important"])

        descending = self.client.get(
            url + _descending_sort_url(ascending, "Strategic Account")
        )
        self.assertEqual(descending.status_code, 200)
        self.assertEqual(_result_names(descending), ["Important", "Plain"])


class RenderedNotSortableColumnTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            "sort-plain", "sort-plain@example.com", "pw"
        )
        self.client.force_login(self.user)

    def test_column_without_admin_order_field_has_no_link(self):
        TargetList.objects.create(name="Newsletter")
        response = self.client.get(reverse("admin:crm_targetlist_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(_sort_url(_column_header(response, "Entries")))

    def test_star_column_renders_and_is_not_sortable(self):
        target_list = TargetList.objects.create(name="Newsletter")
        response = self.client.get(reverse("admin:crm_targetlist_changelist"))
        self.assertEqual(response.status_code, 200)

        toggle_url = reverse(
            "admin:crm_targetlist_subscription_toggle",
            args=["star", target_list.pk],
        )
        self.assertContains(response, toggle_url)

        headers = _header_cells(response)
        name_index = next(
            index
            for index, cell in enumerate(headers)
            if _header_label(cell) == "Name"
        )
        star_header = headers[name_index + 1]
        self.assertEqual(_header_text(star_header), "")
        self.assertIsNone(_sort_url(star_header))
