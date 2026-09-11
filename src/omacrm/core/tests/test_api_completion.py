import json

from django.test import TestCase

from omacrm.core.metadata.registry import registry
from omacrm.core.models import CustomField, User
from omacrm.crm.models import Account


class ApiKeyAuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "api-user", "api@example.com", "pw", api_key="test-api-key"
        )

    def test_api_key_grants_access_without_session(self):
        response = self.client.get("/api/v1/account/", HTTP_X_API_KEY="test-api-key")
        self.assertEqual(response.status_code, 200)

    def test_invalid_api_key_is_rejected(self):
        response = self.client.get("/api/v1/account/", HTTP_X_API_KEY="nope")
        self.assertEqual(response.status_code, 401)

    def test_anonymous_without_key_is_denied(self):
        response = self.client.get("/api/v1/account/")
        self.assertIn(response.status_code, (401, 403))

    def test_portal_api_key_is_still_denied(self):
        User.objects.create_user(
            "portal-key",
            "portal-key@example.com",
            "pw",
            type=User.Type.PORTAL,
            api_key="portal-api-key",
        )
        response = self.client.get(
            "/api/v1/account/", HTTP_X_API_KEY="portal-api-key"
        )
        self.assertEqual(response.status_code, 403)


class WhereFilterTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("filter-api", "fa@example.com", "pw")
        self.client.force_login(self.admin)
        Account.objects.create(name="Acme Inc", type="Customer")
        Account.objects.create(name="Globex", type="Partner")

    def query(self, where):
        return self.client.get(
            "/api/v1/account/", {"where": json.dumps(where)}
        )

    def names(self, response):
        self.assertEqual(response.status_code, 200, response.content)
        return [item["name"] for item in response.json()["results"]]

    def test_equals(self):
        response = self.query(
            [{"type": "equals", "attribute": "name", "value": "Acme Inc"}]
        )
        self.assertEqual(self.names(response), ["Acme Inc"])

    def test_contains(self):
        response = self.query(
            [{"type": "contains", "attribute": "name", "value": "cme"}]
        )
        self.assertEqual(self.names(response), ["Acme Inc"])

    def test_in_and_or_groups(self):
        response = self.query(
            {
                "type": "or",
                "value": [
                    {"type": "equals", "attribute": "type", "value": "Partner"},
                    {"type": "equals", "attribute": "name", "value": "Acme Inc"},
                ],
            }
        )
        self.assertEqual(sorted(self.names(response)), ["Acme Inc", "Globex"])

        response = self.query(
            {
                "type": "and",
                "value": [
                    {"type": "in", "attribute": "name", "value": ["Acme Inc", "Other"]},
                    {"type": "notEquals", "attribute": "name", "value": "Other"},
                ],
            }
        )
        self.assertEqual(self.names(response), ["Acme Inc"])

    def test_not_and_isnull(self):
        response = self.query(
            {
                "type": "not",
                "value": [
                    {"type": "equals", "attribute": "name", "value": "Acme Inc"}
                ],
            }
        )
        self.assertEqual(self.names(response), ["Globex"])

        response = self.query(
            [{"type": "isNull", "attribute": "description", "value": False}]
        )
        self.assertEqual(len(self.names(response)), 2)

    def test_custom_field_filter(self):
        CustomField.objects.create(
            entity_type="Account", name="region", field_type="varchar"
        )
        registry.invalidate()
        Account.objects.create(name="EMEA Co", custom_data={"region": "emea"})

        response = self.query(
            [{"type": "equals", "attribute": "region", "value": "emea"}]
        )
        self.assertIn("EMEA Co", self.names(response))

    def test_invalid_json_returns_400(self):
        response = self.client.get("/api/v1/account/", {"where": "{invalid"})
        self.assertEqual(response.status_code, 400)

    def test_unknown_attribute_returns_400(self):
        response = self.query(
            [{"type": "equals", "attribute": "nope", "value": 1}]
        )
        self.assertEqual(response.status_code, 400)


class GenerateApiKeyActionTests(TestCase):
    def test_action_sets_api_keys(self):
        from unittest.mock import patch

        from django.contrib.admin.sites import site
        from django.test import RequestFactory

        user = User.objects.create_user("keyless", "keyless@example.com", "pw")
        admin_obj = site._registry[User]
        request = RequestFactory().get("/")

        with patch.object(admin_obj, "message_user"):
            admin_obj.generate_api_key(request, User.objects.filter(pk=user.pk))

        user.refresh_from_db()
        self.assertTrue(user.api_key)
