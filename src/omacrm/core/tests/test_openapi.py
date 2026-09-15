from django.test import TestCase
from django.urls import reverse

from omacrm.core.metadata.registry import registry
from omacrm.core.models import (
    CustomEntity,
    CustomField,
    DynamicRecord,
    Role,
    User,
)
from omacrm.core.services import custom_entities


class OpenApiSpecTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "api-docs", "api-docs@example.com", "pw"
        )
        self.client.force_login(self.admin)
        self.url = reverse("openapi_spec")

    def _spec(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_requires_authentication(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_document_structure(self):
        spec = self._spec()
        self.assertEqual(spec["openapi"], "3.1.1")
        self.assertIn("API", spec["info"]["title"])
        self.assertEqual(spec["servers"], [{"url": "/api/v1"}])
        for scheme in ("ApiKeyAuth", "TokenAuth", "SessionAuth"):
            self.assertIn(scheme, spec["components"]["securitySchemes"])
        self.assertEqual(
            spec["components"]["securitySchemes"]["ApiKeyAuth"]["name"],
            "X-Api-Key",
        )
        self.assertEqual(
            spec["security"],
            [{"ApiKeyAuth": []}, {"TokenAuth": []}, {"SessionAuth": []}],
        )

    def test_builtin_entity_paths_and_operations(self):
        spec = self._spec()
        self.assertIn("/account/", spec["paths"])
        self.assertIn("/account/{id}/", spec["paths"])
        self.assertNotIn("/Account/", spec["paths"])
        self.assertEqual(set(spec["paths"]["/account/"]), {"get", "post"})
        self.assertEqual(
            set(spec["paths"]["/account/{id}/"]),
            {"get", "put", "patch", "delete"},
        )
        self.assertEqual(
            spec["paths"]["/account/"]["get"]["operationId"], "account_list"
        )
        self.assertEqual(
            spec["paths"]["/account/{id}/"]["delete"]["responses"]["204"],
            {"description": "Record deleted."},
        )

    def test_field_schema_types_and_enums(self):
        spec = self._spec()
        account = spec["components"]["schemas"]["Account"]["properties"]
        self.assertEqual(account["email_address"]["format"], "email")
        self.assertTrue(account["id"]["readOnly"])
        self.assertTrue(account["created_at"]["readOnly"])
        self.assertEqual(account["assigned_user"]["type"], "integer")

        opportunity = spec["components"]["schemas"]["Opportunity"]["properties"]
        self.assertEqual(opportunity["amount"]["type"], "number")
        self.assertIn("Proposal", opportunity["stage"]["enum"])
        self.assertEqual(opportunity["stage"]["type"], "string")

        task = spec["components"]["schemas"]["Task"]["properties"]
        self.assertEqual(task["date_start"]["type"], "string")
        self.assertEqual(task["date_start"]["format"], "date-time")

    def test_list_parameters_and_paginated_response(self):
        spec = self._spec()
        operation = spec["paths"]["/account/"]["get"]
        self.assertEqual(
            [parameter["name"] for parameter in operation["parameters"]],
            ["limit", "offset", "search", "ordering", "where"],
        )
        self.assertIn("equals", operation["parameters"][-1]["description"])
        self.assertEqual(
            operation["responses"]["200"]["content"]["application/json"]["schema"][
                "$ref"
            ],
            "#/components/schemas/AccountList",
        )
        results = spec["components"]["schemas"]["AccountList"]["properties"]["results"]
        self.assertEqual(results["items"]["$ref"], "#/components/schemas/Account")

    def test_lead_capture_operation_is_public(self):
        spec = self._spec()
        operation = spec["paths"]["/lead-capture/{api_key}/"]["post"]
        self.assertEqual(operation["security"], [])
        submission = spec["components"]["schemas"]["LeadCaptureSubmission"]
        self.assertIn("captcha_token", submission["properties"])
        self.assertIn("503", operation["responses"])

    def test_all_refs_resolve(self):
        spec = self._spec()
        schemas = spec["components"]["schemas"]
        refs = set()

        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == "$ref":
                        refs.add(value)
                    else:
                        walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(spec)
        self.assertTrue(refs)
        for ref in refs:
            self.assertTrue(ref.startswith("#/components/schemas/"))
            self.assertIn(ref.rsplit("/", 1)[-1], schemas)

    def test_dynamic_entity_uses_capitalized_path(self):
        entity = CustomEntity.objects.create(
            name="SpecProject", label="Spec Project", label_plural="Spec Projects"
        )
        CustomField.objects.create(
            entity_type="SpecProject",
            name="status",
            label="Status",
            field_type="enum",
            params={"choices": [["Active", "Active"]]},
        )
        registry.invalidate()
        self.addCleanup(registry.invalidate)
        self.addCleanup(self._cleanup_entity, entity)

        spec = self._spec()
        self.assertIn("/SpecProject/", spec["paths"])
        self.assertNotIn("/specproject/", spec["paths"])
        properties = spec["components"]["schemas"]["SpecProject"]["properties"]
        custom = properties["custom_data"]["properties"]
        self.assertEqual(custom["status"]["enum"], ["Active"])

    def _cleanup_entity(self, entity):
        DynamicRecord.objects.filter(entity_type="SpecProject").delete()
        CustomField.objects.filter(entity_type="SpecProject").delete()
        custom_entities.unregister(entity)
        if entity.pk:
            entity.delete()
        registry.invalidate()

    def test_acl_filters_entities_and_fields(self):
        role = Role.objects.create(
            name="Accounts only",
            data={"Account": {"read": "all"}},
            field_data={"Account": {"email_address": "no"}},
        )
        staff = User.objects.create_user(
            "spec-staff", "spec-staff@example.com", "pw", is_staff=True
        )
        staff.roles.add(role)
        self.client.force_login(staff)

        spec = self._spec()
        self.assertIn("/account/", spec["paths"])
        self.assertNotIn("/opportunity/", spec["paths"])
        properties = spec["components"]["schemas"]["Account"]["properties"]
        self.assertNotIn("email_address", properties)
        self.assertIn("name", properties)
