from django.test import TestCase
from django.urls import reverse

from omacrm.core.models import AppSecret, User
from omacrm.core.services import secrets
from omacrm.core.services.formula import build_context, evaluate


class AppSecretServiceTests(TestCase):
    def test_set_stores_ciphertext_and_get_round_trips(self):
        secrets.set("API_KEY", "super-secret")
        row = AppSecret.objects.get(name="API_KEY")
        self.assertNotEqual(row.value, "super-secret")
        self.assertNotIn("super-secret", row.value)
        self.assertEqual(secrets.get("API_KEY"), "super-secret")

    def test_get_unknown_name_is_empty(self):
        self.assertEqual(secrets.get("NOPE"), "")

    def test_get_with_undecryptable_value_is_empty(self):
        AppSecret.objects.create(name="BROKEN", value="not-a-fernet-token")
        self.assertEqual(secrets.get("BROKEN"), "")

    def test_set_updates_the_existing_secret(self):
        first = secrets.set("API_KEY", "one")
        updated = secrets.set("API_KEY", "two", description="second")
        self.assertEqual(updated.pk, first.pk)
        self.assertEqual(AppSecret.objects.count(), 1)
        self.assertEqual(secrets.get("API_KEY"), "two")
        self.assertEqual(updated.description, "second")

    def test_names_are_sorted(self):
        secrets.set("B", "1")
        secrets.set("A", "2")
        self.assertEqual(secrets.names(), ["A", "B"])

    def test_str_does_not_expose_the_value(self):
        row = secrets.set("API_KEY", "super-secret")
        self.assertEqual(str(row), "API_KEY")
        self.assertNotIn("super-secret", str(row))


class AppSecretFormulaTests(TestCase):
    def test_secret_is_available_to_formulas(self):
        secrets.set("API_KEY", "formula-secret")
        context = build_context(AppSecret())
        self.assertEqual(evaluate("secret('API_KEY')", context), "formula-secret")

    def test_missing_secret_returns_empty_string(self):
        context = build_context(AppSecret())
        self.assertEqual(evaluate("secret('NOPE')", context), "")


class AppSecretAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "secret-admin", "secret@example.com", "pw"
        )
        self.client.force_login(self.admin)

    def test_admin_encrypts_on_save(self):
        response = self.client.post(
            reverse("admin:core_appsecret_add"),
            data={"name": "PAYMENT_KEY", "secret": "plain-value", "description": "d"},
        )
        self.assertEqual(response.status_code, 302)
        row = AppSecret.objects.get(name="PAYMENT_KEY")
        self.assertNotEqual(row.value, "plain-value")
        self.assertEqual(row.get_value(), "plain-value")

    def test_admin_blank_keeps_the_current_value(self):
        row = secrets.set("PAYMENT_KEY", "plain-value")
        response = self.client.post(
            reverse("admin:core_appsecret_change", args=[row.pk]),
            data={"name": "PAYMENT_KEY", "secret": "", "description": "updated"},
        )
        self.assertEqual(response.status_code, 302)
        row.refresh_from_db()
        self.assertEqual(row.get_value(), "plain-value")
        self.assertEqual(row.description, "updated")

    def test_admin_pages_never_render_the_plaintext(self):
        row = secrets.set("PAYMENT_KEY", "plain-value")
        response = self.client.get(
            reverse("admin:core_appsecret_change", args=[row.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "plain-value")
        self.assertNotContains(response, row.value)
