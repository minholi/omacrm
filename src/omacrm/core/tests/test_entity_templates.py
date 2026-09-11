from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from omacrm.core.metadata.registry import registry
from omacrm.core.models import CustomEntity, CustomField, DynamicRecord, Layout, User
from omacrm.core.services import custom_entities

FIELD_PREFIX = "custom__"


class EntityTemplateTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "tpl-admin", "tpl@example.com", "pw"
        )
        self.client.force_login(self.admin)
        self.addCleanup(registry.invalidate)
        self.entities = []

    def _entity(self, name, template, **extra):
        entity = CustomEntity.objects.create(
            name=name,
            label=name,
            label_plural=f"{name}s",
            template=template,
            **extra,
        )
        self.entities.append(entity)
        self.addCleanup(self._cleanup, entity)
        registry.invalidate()
        return entity

    def _cleanup(self, entity):
        DynamicRecord.objects.filter(entity_type=entity.name).delete()
        Layout.objects.filter(entity_type=entity.name).delete()
        CustomField.objects.filter(entity_type=entity.name).delete()
        custom_entities.unregister(entity)
        if entity.pk:
            entity.delete()
        registry.invalidate()

    def test_base_template_only_creates_entity(self):
        self._entity("Asset", "base")
        self.assertFalse(CustomField.objects.filter(entity_type="Asset").exists())
        self.assertFalse(Layout.objects.filter(entity_type="Asset").exists())

    def test_person_template_creates_fields_layouts_and_name(self):
        self._entity("Candidate", "person")
        field_types = dict(
            CustomField.objects.filter(entity_type="Candidate").values_list(
                "name", "field_type"
            )
        )
        self.assertEqual(field_types["first_name"], "varchar")
        self.assertEqual(field_types["phone_number"], "phone")
        self.assertEqual(field_types["address"], "address")
        self.assertTrue(
            Layout.objects.filter(entity_type="Candidate", layout_name="detail").exists()
        )
        entity = CustomEntity.objects.get(name="Candidate")
        self.assertEqual(entity.icon, "person")

        record = custom_entities.get_proxy("Candidate").objects.create(
            entity_type="Candidate",
            custom_data={"first_name": "Ada", "last_name": "Lovelace"},
        )
        self.assertEqual(record.name, "Ada Lovelace")

        record.custom_data = {"first_name": "Ada", "last_name": "Byron"}
        record.save()
        record.refresh_from_db()
        self.assertEqual(record.name, "Ada Byron")

    def test_company_template_fields(self):
        self._entity("Vendor", "company")
        names = set(
            CustomField.objects.filter(entity_type="Vendor").values_list(
                "name", flat=True
            )
        )
        self.assertIn("website", names)
        self.assertIn("billing_address", names)
        self.assertEqual(CustomEntity.objects.get(name="Vendor").icon, "domain")

    def test_event_template_appears_on_calendar(self):
        self._entity("Session", "event")
        entity = CustomEntity.objects.get(name="Session")
        self.assertTrue(entity.show_in_calendar)
        self.assertEqual(entity.icon, "event")

        now = timezone.localtime()
        custom_entities.get_proxy("Session").objects.create(
            entity_type="Session",
            name="Onboarding workshop",
            assigned_user=self.admin,
            custom_data={
                "status": "Planned",
                "date_start": now.isoformat(),
                "date_end": now.isoformat(),
            },
        )

        response = self.client.get(reverse("crm_calendar"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Onboarding workshop")

    def test_template_is_locked_after_creation(self):
        entity = self._entity("Candidate", "person")
        entity.template = "company"
        entity.save()
        entity.refresh_from_db()
        self.assertEqual(entity.template, CustomEntity.Template.PERSON)

        response = self.client.get(
            reverse("admin:core_customentity_change", args=[entity.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "person", status_code=200)
