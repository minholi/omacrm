from django.test import TestCase

from omacrm.core.services.phone import format_phone, is_valid_phone, normalize_phone
from omacrm.crm.models import Account, Contact, Lead


class PhoneServiceTests(TestCase):
    def test_normalize_with_explicit_region(self):
        self.assertEqual(
            normalize_phone("11 91234-5678", region="BR"), "+5511912345678"
        )

    def test_normalize_us_number(self):
        self.assertEqual(normalize_phone("+1 415 555 2671"), "+14155552671")

    def test_invalid_value_is_preserved(self):
        self.assertEqual(normalize_phone("not a phone"), "not a phone")

    def test_format_styles(self):
        self.assertEqual(format_phone("+14155552671", style="e164"), "+14155552671")
        self.assertEqual(
            format_phone("+14155552671", style="national"), "(415) 555-2671"
        )

    def test_is_valid(self):
        self.assertTrue(is_valid_phone("+14155552671"))
        self.assertFalse(is_valid_phone("123"))


class PhoneNormalizationHookTests(TestCase):
    def setUp(self):
        from constance import config

        self.config = config
        self.config.phone_default_region = "BR"
        self.addCleanup(setattr, self.config, "phone_default_region", "US")

    def test_contact_phone_normalized(self):
        contact = Contact.objects.create(
            first_name="Ana", last_name="Silva", phone_number="11 91234-5678"
        )
        contact.refresh_from_db()
        self.assertEqual(contact.phone_number, "+5511912345678")

    def test_account_and_lead_phone_normalized(self):
        account = Account.objects.create(name="Phone Co", phone_number="11 91234-5678")
        lead = Lead.objects.create(
            first_name="Phone", last_name="Lead", phone_number="11 91234-5678"
        )
        account.refresh_from_db()
        lead.refresh_from_db()
        self.assertEqual(account.phone_number, "+5511912345678")
        self.assertEqual(lead.phone_number, "+5511912345678")

    def test_invalid_phone_is_kept(self):
        contact = Contact.objects.create(
            first_name="No", last_name="Phone", phone_number="extension 42"
        )
        contact.refresh_from_db()
        self.assertEqual(contact.phone_number, "extension 42")
