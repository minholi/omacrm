import importlib

from django.contrib import admin
from django.test import TestCase
from django.urls import clear_url_caches, reverse

from omacrm.core.metadata.registry import registry
from omacrm.core.models import CustomEntity, CustomField, DynamicRecord, Note, User
from omacrm.core.services import custom_entities

ATTACHMENT_PREFIX = "core-attachment-related_type-related_id"


def reload_admin_urls():
    """Runtime admin registrations need a fresh URLconf (normally a restart)."""

    import omacrm.config.urls

    importlib.reload(omacrm.config.urls)
    clear_url_caches()


class CustomEntityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("entity-admin", "ce@example.com", "pw")
        self.client.force_login(self.admin)
        self.entity = CustomEntity.objects.create(
            name="Project", label="Project", label_plural="Projects"
        )
        reload_admin_urls()
        self.addCleanup(self._cleanup, self.entity)

    def _cleanup(self, entity):
        DynamicRecord.objects.filter(entity_type=entity.name).delete()
        Note.objects.filter(parent_type__model=entity.name.lower()).delete()
        CustomField.objects.filter(entity_type=entity.name).delete()
        custom_entities.unregister(entity)
        if entity.pk:
            entity.delete()
        registry.invalidate()

    def _add_form_data(self, **extra):
        data = {
            "name": "Apollo",
            "assigned_user": "",
            "teams": [],
            "_save": "Save",
            f"{ATTACHMENT_PREFIX}-TOTAL_FORMS": "0",
            f"{ATTACHMENT_PREFIX}-INITIAL_FORMS": "0",
            f"{ATTACHMENT_PREFIX}-MIN_NUM_FORMS": "0",
            f"{ATTACHMENT_PREFIX}-MAX_NUM_FORMS": "1000",
        }
        data.update(extra)
        return data

    def test_materialize_registers_entity_and_admin(self):
        registry.invalidate()
        self.assertTrue(registry.has("Project"))
        self.assertTrue(registry.is_dynamic("Project"))
        self.assertIn("Project", registry.entity_types())

        proxy = custom_entities.get_proxy("Project")
        self.assertTrue(admin.site.is_registered(proxy))
        self.assertEqual(proxy._meta.proxy, True)

    def test_registry_fields_include_base_and_custom(self):
        CustomField.objects.create(
            entity_type="Project", name="code", field_type="varchar", label="Code"
        )
        registry.invalidate()
        fields = registry.fields("Project")
        self.assertIn("name", fields)
        self.assertIn("assigned_user", fields)
        self.assertIn("code", fields)
        self.assertTrue(fields["code"].custom)

    def test_admin_creates_record_with_custom_data(self):
        CustomField.objects.create(
            entity_type="Project", name="code", field_type="varchar", label="Code"
        )
        registry.invalidate()
        url = reverse("admin:core_project_add")
        response = self.client.post(
            url, self._add_form_data(**{"custom__code": "P-1"})
        )
        self.assertEqual(response.status_code, 302, response.content)

        record = DynamicRecord.objects.get(entity_type="Project")
        self.assertEqual(record.name, "Apollo")
        self.assertEqual(record.custom_data, {"code": "P-1"})
        self.assertTrue(
            Note.objects.filter(
                parent_id=record.pk, parent_type__model="project"
            ).exists()
        )

    def test_changelist_and_change_page_render(self):
        self.assertEqual(
            self.client.get(reverse("admin:core_project_changelist")).status_code, 200
        )
        record = DynamicRecord.objects.create(entity_type="Project", name="Apollo")
        response = self.client.get(
            reverse("admin:core_project_change", args=[record.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_deactivating_unregisters(self):
        self.entity.is_active = False
        self.entity.save()
        registry.invalidate()
        proxy = custom_entities.get_proxy("Project")
        self.assertFalse(registry.has("Project"))
        self.assertFalse(admin.site.is_registered(proxy))
        self.entity.is_active = True
        self.entity.save()
        registry.invalidate()
        self.assertTrue(registry.has("Project"))

    def test_deleting_entity_removes_stream_and_content_type(self):
        from django.contrib.contenttypes.models import ContentType

        proxy = custom_entities.get_proxy("Project")
        record = proxy.objects.create(entity_type="Project", name="Temp")
        content_type = ContentType.objects.get_for_model(
            proxy, for_concrete_model=False
        )
        self.assertTrue(
            Note.objects.filter(parent_type=content_type, parent_id=record.pk).exists()
        )

        self.entity.delete()
        registry.invalidate()

        self.assertFalse(
            Note.objects.filter(parent_type_id=content_type.pk).exists()
        )
        self.assertFalse(
            ContentType.objects.filter(pk=content_type.pk).exists()
        )
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_name_validation(self):
        from django.core.exceptions import ValidationError

        for bad_name in ("project", "1Project", "Pro ject", "Account"):
            entity = CustomEntity(name=bad_name)
            with self.assertRaises(ValidationError, msg=bad_name):
                entity.full_clean()
