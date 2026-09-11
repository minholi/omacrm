from django.test import TestCase

from omacrm.core.metadata.registry import registry
from omacrm.core.models import CustomField, Layout


class MetadataRegistryTests(TestCase):
    def setUp(self):
        registry.invalidate()

    def test_builtin_entities_registered(self):
        entity_types = registry.entity_types()
        self.assertIn("User", entity_types)
        self.assertIn("Team", entity_types)
        self.assertIn("Role", entity_types)

    def test_custom_field_merge(self):
        CustomField.objects.create(
            entity_type="Team",
            name="region",
            field_type=CustomField.FieldType.ENUM,
            label="Region",
            params={"choices": [["emea", "EMEA"], ["amer", "AMER"]]},
        )
        fields = registry.fields("Team")
        self.assertIn("region", fields)
        self.assertTrue(fields["region"].custom)
        self.assertEqual(fields["region"].display_label, "Region")

    def test_layout_override(self):
        Layout.objects.create(
            entity_type="Team",
            layout_name="detail",
            data=[{"title": "Custom section", "fields": ["name"]}],
        )
        layout = registry.layout("Team", "detail")
        self.assertEqual(layout[0]["title"], "Custom section")

    def test_entity_type_for_instance(self):
        from omacrm.core.models import Team

        self.assertEqual(registry.entity_type_for_instance(Team(name="x")), "Team")

    def test_custom_field_clean_rejects_builtin_collision(self):
        from django.core.exceptions import ValidationError

        field = CustomField(entity_type="Team", name="name", field_type="varchar")
        with self.assertRaises(ValidationError):
            field.full_clean()
