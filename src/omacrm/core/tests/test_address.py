from django.test import TestCase

from omacrm.core.services.address import (
    format_address,
    format_address_values,
    get_address_values,
)
from omacrm.crm.models import Account, Contact


class AddressServiceTests(TestCase):
    def test_format_billing_address(self):
        account = Account.objects.create(
            name="Address Co",
            billing_address_street="1 Main St",
            billing_address_city="Springfield",
            billing_address_state="IL",
            billing_address_postal_code="62701",
            billing_address_country="USA",
        )
        self.assertEqual(
            format_address(account, "billing_"),
            "1 Main St, Springfield, IL, 62701, USA",
        )

    def test_missing_parts_are_skipped(self):
        contact = Contact.objects.create(
            first_name="Ana", last_name="Silva", address_city="Rio", address_country="Brazil"
        )
        self.assertEqual(format_address(contact), "Rio, Brazil")

    def test_empty_address(self):
        account = Account.objects.create(name="Empty")
        self.assertEqual(format_address(account, "shipping_"), "")

    def test_custom_separator_and_order(self):
        self.assertEqual(
            format_address_values(
                city="Rio", country="Brazil", separator=" - ", order=("country", "city")
            ),
            "Brazil - Rio",
        )

    def test_get_address_values(self):
        account = Account.objects.create(name="Values", shipping_address_city="Oslo")
        values = get_address_values(account, "shipping_")
        self.assertEqual(values["city"], "Oslo")
        self.assertEqual(values["street"], "")
