"""Entity display names come from the metadata, not the model ``Meta``.

Django derives `_meta.verbose_name_plural` from the class name, so the admin
titles and breadcrumbs said "Opportunitys" while the metadata (and the
sidebar) said "Opportunities". The registry mirrors the metadata labels onto
`_meta`, which leaves `_meta.original_attrs` (what migrations serialize) alone.
"""

import importlib

from django.apps import apps
from django.test import TestCase
from django.urls import clear_url_caches, reverse

from omacrm.core.metadata.registry import registry
from omacrm.core.models import CustomEntity, User
from omacrm.core.services import custom_entities


class MetadataLabelMirrorTests(TestCase):
    def setUp(self):
        registry.invalidate()

    def test_every_metadata_entity_mirrors_its_labels(self):
        mismatches = {}
        for entity_type, entity in registry.entities().items():
            model = apps.get_model(entity.model)
            actual = (
                str(model._meta.verbose_name),
                str(model._meta.verbose_name_plural),
            )
            expected = (
                str(entity.display_label),
                str(entity.display_label_plural),
            )
            if actual != expected:
                mismatches[entity_type] = (actual, expected)
        self.assertEqual(mismatches, {})


class OpportunityChangelistTests(TestCase):
    def setUp(self):
        user = User.objects.create_superuser(
            "label-admin", "labels@example.com", "pw"
        )
        self.client.force_login(user)

    def test_changelist_uses_the_metadata_plural(self):
        response = self.client.get(reverse("admin:crm_opportunity_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Opportunities")
        self.assertNotContains(response, "Opportunitys")


class CustomEntityLabelTests(TestCase):
    def setUp(self):
        user = User.objects.create_superuser(
            "initiative-admin", "initiative@example.com", "pw"
        )
        self.client.force_login(user)
        self.entity = CustomEntity.objects.create(
            name="Initiative", label="Initiative", label_plural="Programs"
        )
        import omacrm.config.urls

        importlib.reload(omacrm.config.urls)
        clear_url_caches()
        self.addCleanup(self._cleanup, self.entity)

    def _cleanup(self, entity):
        custom_entities.unregister(entity)
        if entity.pk:
            entity.delete()
        registry.invalidate()

    def test_custom_entity_registers_and_renders_its_label(self):
        self.assertTrue(registry.has("Initiative"))
        self.assertEqual(
            apps.get_model("core", "Initiative")._meta.verbose_name_plural,
            "Programs",
        )

        response = self.client.get(reverse("admin:core_initiative_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Programs")
        self.assertNotContains(response, "Initiatives")
