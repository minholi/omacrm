from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from omacrm.core.metadata.registry import registry
from omacrm.core.models import (
    CustomEntity,
    CustomField,
    CustomLink,
    DynamicRecord,
    Layout,
    User,
)
from omacrm.core.services import custom_entities

ENTITIES_URL = "/api/v1/metadata/entities/"
FIELDS_URL = "/api/v1/metadata/fields/"
LAYOUTS_URL = "/api/v1/metadata/layouts/"
LINKS_URL = "/api/v1/metadata/links/"


class MetadataApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "meta-admin", "meta@example.com", "pw"
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.addCleanup(registry.invalidate)

    def _cleanup_entity(self, name):
        entity = CustomEntity.objects.filter(name=name).first()
        if entity is not None:
            custom_entities.unregister(entity)
            entity.delete()
        DynamicRecord.objects.filter(entity_type=name).delete()
        CustomField.objects.filter(entity_type=name).delete()
        Layout.objects.filter(entity_type=name).delete()
        CustomLink.objects.filter(entity_type=name).delete()
        CustomLink.objects.filter(link_entity=name).delete()
        registry.invalidate()

    def _create_entity(self, name, **extra):
        self.addCleanup(self._cleanup_entity, name)
        payload = {"name": name, "label": name, "label_plural": f"{name}s"}
        payload.update(extra)
        response = self.client.post(ENTITIES_URL, payload, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def test_requires_authentication(self):
        self.assertEqual(APIClient().get(ENTITIES_URL).status_code, 401)

    def test_requires_staff(self):
        user = User.objects.create_user(
            "meta-user", "meta-user@example.com", "pw"
        )
        client = APIClient()
        client.force_authenticate(user)
        self.assertEqual(client.get(ENTITIES_URL).status_code, 403)
        self.assertEqual(
            client.post(ENTITIES_URL, {"name": "Nope"}, format="json").status_code,
            403,
        )

    def test_entity_crud_and_record_api_available_immediately(self):
        entity = self._create_entity("Widget", label="Widget", label_plural="Widgets")
        entity_id = entity["id"]

        response = self.client.post(
            "/api/v1/Widget/", {"name": "Gizmo"}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(self.client.get("/api/v1/Widget/").json()["count"], 1)

        response = self.client.patch(
            f"{ENTITIES_URL}{entity_id}/", {"label": "Widgy"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(CustomEntity.objects.get(pk=entity_id).label, "Widgy")

        response = self.client.delete(f"{ENTITIES_URL}{entity_id}/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get("/api/v1/Widget/").status_code, 404)

    def test_entity_name_and_template_are_locked(self):
        entity = self._create_entity("Gadget")
        url = f"{ENTITIES_URL}{entity['id']}/"

        response = self.client.patch(url, {"name": "Gizmo"}, format="json")
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("name", response.json())

        response = self.client.patch(url, {"template": "person"}, format="json")
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("template", response.json())

    def test_entity_validation_errors(self):
        response = self.client.post(
            ENTITIES_URL, {"name": "bad_name"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json())

        response = self.client.post(ENTITIES_URL, {"name": "User"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json())

        response = self.client.post(
            ENTITIES_URL, {"name": "Duplicate"}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.addCleanup(self._cleanup_entity, "Duplicate")
        response = self.client.post(
            ENTITIES_URL, {"name": "Duplicate"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_field_crud(self):
        self._create_entity("Asset")
        response = self.client.post(
            FIELDS_URL,
            {
                "entity_type": "Asset",
                "name": "code",
                "label": "Code",
                "field_type": "varchar",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        field_id = response.json()["id"]

        response = self.client.post(
            "/api/v1/Asset/",
            {"name": "Laptop", "custom_data": {"code": "A-1"}},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        record = DynamicRecord.objects.get(name="Laptop")
        self.assertEqual(record.custom_data["code"], "A-1")

        response = self.client.patch(
            f"{FIELDS_URL}{field_id}/", {"label": "Asset code"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            CustomField.objects.get(pk=field_id).label, "Asset code"
        )

        self.assertEqual(
            self.client.delete(f"{FIELDS_URL}{field_id}/").status_code, 204
        )
        self.assertFalse(CustomField.objects.filter(pk=field_id).exists())

    def test_field_unknown_entity_rejected(self):
        response = self.client.post(
            FIELDS_URL,
            {"entity_type": "Nope", "name": "code", "field_type": "varchar"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("entity_type", response.json())

    def test_field_invalid_name_rejected(self):
        self._create_entity("Asset")
        response = self.client.post(
            FIELDS_URL,
            {"entity_type": "Asset", "name": "Bad Name", "field_type": "varchar"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json())

    def test_layout_crud(self):
        self._create_entity("Board")
        response = self.client.post(
            LAYOUTS_URL,
            {
                "entity_type": "Board",
                "layout_name": "list",
                "data": ["name"],
                "is_custom": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        layout_id = response.json()["id"]

        response = self.client.patch(
            f"{LAYOUTS_URL}{layout_id}/", {"data": ["name", "created_at"]}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            Layout.objects.get(pk=layout_id).data, ["name", "created_at"]
        )

        self.assertEqual(
            self.client.delete(f"{LAYOUTS_URL}{layout_id}/").status_code, 204
        )

    def test_link_crud(self):
        self._create_entity("Asset")
        self._create_entity("Vendor")
        response = self.client.post(
            LINKS_URL,
            {
                "entity_type": "Asset",
                "name": "vendor",
                "link_type": "belongsTo",
                "link_entity": "Vendor",
                "foreign_name": "assets",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        link_id = response.json()["id"]

        response = self.client.get(LINKS_URL, {"search": "Asset"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

        self.assertEqual(
            self.client.delete(f"{LINKS_URL}{link_id}/").status_code, 204
        )
        self.assertFalse(CustomLink.objects.filter(pk=link_id).exists())

    def test_openapi_includes_metadata_for_staff_only(self):
        self.client.force_login(self.admin)
        spec = self.client.get(reverse("openapi_spec")).json()
        self.assertIn("/metadata/entities/", spec["paths"])
        self.assertIn("/metadata/fields/", spec["paths"])
        self.assertIn("/metadata/layouts/", spec["paths"])
        self.assertIn("/metadata/links/", spec["paths"])
        self.assertIn("CustomEntity", spec["components"]["schemas"])
        self.assertIn(
            "Metadata", [tag["name"] for tag in spec["tags"]]
        )
        self.assertNotIn("where", {
            parameter["name"]
            for parameter in spec["paths"]["/metadata/entities/"]["get"]["parameters"]
        })

        user = User.objects.create_user("meta-doc", "meta-doc@example.com", "pw")
        client = APIClient()
        client.force_login(user)
        spec = client.get(reverse("openapi_spec")).json()
        self.assertNotIn("/metadata/entities/", spec["paths"])
        self.assertNotIn("CustomEntity", spec["components"]["schemas"])
