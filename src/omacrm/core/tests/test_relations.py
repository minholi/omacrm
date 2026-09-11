from django.test import TestCase
from django.urls import reverse

from omacrm.core.metadata.registry import registry
from omacrm.core.models import (
    CustomEntity,
    CustomLink,
    Layout,
    RecordLink,
    Role,
    User,
)
from omacrm.core.services import custom_entities, relations
from omacrm.crm.models import Account, Contact

ATTACHMENT_PREFIX = "core-attachment-related_type-related_id"


class RelationServiceTests(TestCase):
    def setUp(self):
        self.entity = CustomEntity.objects.create(
            name="Project", label="Project", label_plural="Projects"
        )
        self.account_link = CustomLink.objects.create(
            entity_type="Project",
            name="account",
            link_type="belongsTo",
            link_entity="Account",
            label="Account",
        )
        self.contacts_link = CustomLink.objects.create(
            entity_type="Project",
            name="contacts",
            link_type="manyToMany",
            link_entity="Contact",
            label="Team",
        )
        registry.invalidate()
        self.account = Account.objects.create(name="Acme")
        self.other_account = Account.objects.create(name="Globex")
        self.contacts = [
            Contact.objects.create(first_name="Ana", last_name="One"),
            Contact.objects.create(first_name="Bruno", last_name="Two"),
        ]
        proxy = custom_entities.get_proxy("Project")
        self.project = proxy.objects.create(entity_type="Project", name="Apollo")
        self.addCleanup(registry.invalidate)
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        from omacrm.core.models import DynamicRecord

        DynamicRecord.objects.filter(entity_type="Project").delete()
        CustomLink.objects.filter(entity_type="Project").delete()
        custom_entities.unregister(self.entity)
        if self.entity.pk:
            self.entity.delete()
        registry.invalidate()

    def test_link_definitions_expose_both_sides(self):
        project_defs = registry.link_definitions("Project")
        self.assertEqual(project_defs["account"].link_type, "belongsTo")
        self.assertEqual(project_defs["account"].foreign_name, "projects")
        self.assertEqual(project_defs["contacts"].link_type, "manyToMany")

        account_defs = registry.link_definitions("Account")
        self.assertEqual(account_defs["projects"].link_type, "hasMany")
        self.assertEqual(account_defs["projects"].target_entity, "Project")
        self.assertTrue(account_defs["projects"].multiple)

        contact_defs = registry.link_definitions("Contact")
        self.assertEqual(contact_defs["projects"].link_type, "manyToMany")

        fields = registry.link_fields("Project")
        self.assertEqual(fields["account"].type, "link")
        self.assertEqual(fields["contacts"].type, "linkMultiple")

    def test_add_and_reverse_links(self):
        relations.add_related(self.project, "account", self.account)
        relations.add_related(self.project, "contacts", self.contacts[0])

        self.assertEqual(
            [record.name for record in relations.get_related(self.project, "account")],
            ["Acme"],
        )
        self.assertEqual(
            [record.name for record in relations.get_related(self.project, "contacts")],
            ["Ana One"],
        )
        reverse = relations.get_related(self.account, "projects")
        self.assertEqual([record.name for record in reverse], ["Apollo"])
        self.assertEqual(
            [
                record.name
                for record in relations.get_related(self.contacts[0], "projects")
            ],
            ["Apollo"],
        )
        self.assertEqual(RecordLink.objects.count(), 4)

    def test_belongs_to_keeps_single_target(self):
        relations.add_related(self.project, "account", self.account)
        relations.add_related(self.project, "account", self.other_account)
        self.assertEqual(
            [record.name for record in relations.get_related(self.project, "account")],
            ["Globex"],
        )
        self.assertEqual(relations.get_related(self.account, "projects"), [])

    def test_set_and_clear_links(self):
        relations.set_related(
            self.project, "contacts", [self.contacts[0], self.contacts[1]]
        )
        self.assertEqual(len(relations.get_related(self.project, "contacts")), 2)

        relations.set_related(self.project, "contacts", [self.contacts[1]])
        names = [
            record.name for record in relations.get_related(self.project, "contacts")
        ]
        self.assertEqual(names, ["Bruno Two"])

        relations.clear_related(self.project, "contacts")
        self.assertEqual(relations.get_related(self.project, "contacts"), [])
        self.assertEqual(RecordLink.objects.count(), 0)

    def test_related_map_batches(self):
        relations.add_related(self.project, "contacts", self.contacts[0])
        other = custom_entities.get_proxy("Project").objects.create(
            entity_type="Project", name="Zeus"
        )
        relations.add_related(other, "contacts", self.contacts[1])
        mapping = relations.related_map([self.project, other], "contacts")
        self.assertEqual(mapping[self.project.pk][0].name, "Ana One")
        self.assertEqual(mapping[other.pk][0].name, "Bruno Two")


class RelationAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "rel-admin", "rel@example.com", "pw"
        )
        self.client.force_login(self.admin)
        self.entity = CustomEntity.objects.create(
            name="Project", label="Project", label_plural="Projects"
        )
        CustomLink.objects.create(
            entity_type="Project",
            name="account",
            link_type="belongsTo",
            link_entity="Account",
            label="Account",
        )
        registry.invalidate()
        self.account = Account.objects.create(name="Acme")
        self.addCleanup(registry.invalidate)
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        from omacrm.core.models import DynamicRecord

        DynamicRecord.objects.filter(entity_type="Project").delete()
        Layout.objects.filter(entity_type="Project").delete()
        CustomLink.objects.filter(entity_type="Project").delete()
        custom_entities.unregister(self.entity)
        if self.entity.pk:
            self.entity.delete()
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

    def test_add_form_creates_link(self):
        response = self.client.post(
            reverse("admin:core_project_add"),
            self._add_form_data(**{"link__account": self.account.pk}),
        )
        self.assertEqual(response.status_code, 302, response.content)
        record = custom_entities.get_proxy("Project").objects.get(name="Apollo")
        self.assertEqual(
            [row.name for row in relations.get_related(record, "account")],
            ["Acme"],
        )
        self.assertEqual(
            [row.name for row in relations.get_related(self.account, "projects")],
            ["Apollo"],
        )

    def test_change_form_prefills_link(self):
        record = custom_entities.get_proxy("Project").objects.create(
            entity_type="Project", name="Apollo"
        )
        relations.add_related(record, "account", self.account)

        response = self.client.get(
            reverse("admin:core_project_change", args=[record.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="link__account"')
        self.assertContains(response, f'value="{self.account.pk}" selected')

    def test_list_layout_shows_link_column(self):
        record = custom_entities.get_proxy("Project").objects.create(
            entity_type="Project", name="Apollo"
        )
        relations.add_related(record, "account", self.account)
        Layout.objects.create(
            entity_type="Project",
            layout_name="list",
            data=["name", "account"],
            is_custom=True,
        )
        registry.invalidate()

        response = self.client.get(reverse("admin:core_project_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Acme")
        self.assertContains(response, "Account")


class RelationApiTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient

        self.admin = User.objects.create_superuser(
            "rel-api", "rel-api@example.com", "pw"
        )
        self.entity = CustomEntity.objects.create(
            name="Project", label="Project", label_plural="Projects"
        )
        CustomLink.objects.create(
            entity_type="Project",
            name="account",
            link_type="belongsTo",
            link_entity="Account",
            label="Account",
        )
        registry.invalidate()
        self.account = Account.objects.create(name="Acme")
        self.other_account = Account.objects.create(name="Globex")
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.addCleanup(registry.invalidate)
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        from omacrm.core.models import DynamicRecord

        DynamicRecord.objects.filter(entity_type="Project").delete()
        CustomLink.objects.filter(entity_type="Project").delete()
        custom_entities.unregister(self.entity)
        if self.entity.pk:
            self.entity.delete()
        registry.invalidate()

    def test_api_reads_and_writes_links(self):
        response = self.client.post(
            "/api/v1/Project/",
            {"name": "Apollo", "account": self.account.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        record_id = response.json()["id"]
        self.assertEqual(response.json()["account"], self.account.pk)

        record = custom_entities.get_proxy("Project").objects.get(pk=record_id)
        self.assertEqual(
            [row.name for row in relations.get_related(record, "account")],
            ["Acme"],
        )

        detail_url = f"/api/v1/Project/{record_id}/"
        response = self.client.patch(
            detail_url, {"account": self.other_account.pk}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["account"], self.other_account.pk)
        record.refresh_from_db()
        self.assertEqual(
            [row.name for row in relations.get_related(record, "account")],
            ["Globex"],
        )

        response = self.client.get(detail_url)
        self.assertEqual(response.json()["account"], self.other_account.pk)


class LinkAutocompleteTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "link-auto", "link-auto@example.com", "pw"
        )
        self.client.force_login(self.admin)
        self.entity = CustomEntity.objects.create(
            name="Project", label="Project", label_plural="Projects"
        )
        CustomLink.objects.create(
            entity_type="Project",
            name="account",
            link_type="belongsTo",
            link_entity="Account",
            label="Account",
        )
        registry.invalidate()
        self.acme = Account.objects.create(name="Acme")
        self.globex = Account.objects.create(name="Globex")
        Account.objects.create(name="Initech")
        self.addCleanup(registry.invalidate)
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        from omacrm.core.models import DynamicRecord

        DynamicRecord.objects.filter(entity_type="Project").delete()
        CustomLink.objects.filter(entity_type="Project").delete()
        custom_entities.unregister(self.entity)
        if self.entity.pk:
            self.entity.delete()
        registry.invalidate()

    def test_autocomplete_filters_by_term(self):
        response = self.client.get(
            reverse("link_autocomplete"),
            {"entity_type": "Account", "term": "glo"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            [item["text"] for item in payload["results"]], ["Globex"]
        )
        self.assertEqual(payload["results"][0]["id"], str(self.globex.pk))

    def test_autocomplete_requires_read_access(self):
        role = Role.objects.create(
            name="No accounts", data={"Account": {"read": "no"}}
        )
        staff = User.objects.create_user(
            "link-staff", "link-staff@example.com", "pw", is_staff=True
        )
        staff.roles.add(role)
        self.client.force_login(staff)
        response = self.client.get(
            reverse("link_autocomplete"), {"entity_type": "Account"}
        )
        self.assertEqual(response.status_code, 403)

    def test_autocomplete_unknown_entity_returns_404(self):
        self.assertEqual(
            self.client.get(
                reverse("link_autocomplete"), {"entity_type": "Nope"}
            ).status_code,
            404,
        )

    def test_link_picker_only_renders_linked_options(self):
        record = custom_entities.get_proxy("Project").objects.create(
            entity_type="Project", name="Apollo"
        )
        relations.add_related(record, "account", self.acme)

        response = self.client.get(
            reverse("admin:core_project_change", args=[record.pk])
        )
        content = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn("data-ajax--url", content)
        self.assertIn("entity_type=Account", content)
        self.assertIn("Acme", content)
        self.assertNotIn("Globex", content)
        self.assertNotIn("Initech", content)


class CustomLinkValidationTests(TestCase):
    def test_invalid_names_and_entities(self):
        from django.core.exceptions import ValidationError

        invalid = (
            {"entity_type": "Account", "name": "BadName", "link_entity": "Contact"},
            {"entity_type": "Account", "name": "ok", "link_entity": "Nope"},
            {"entity_type": "Nope", "name": "ok", "link_entity": "Contact"},
            {"entity_type": "Account", "name": "name", "link_entity": "Contact"},
        )
        for data in invalid:
            link = CustomLink(link_type="belongsTo", foreign_name="rev", **data)
            with self.assertRaises(ValidationError, msg=data):
                link.full_clean()

    def test_foreign_name_is_derived(self):
        link = CustomLink.objects.create(
            entity_type="Account",
            name="projects",
            link_type="hasMany",
            link_entity="Contact",
        )
        self.assertEqual(link.foreign_name, "accounts")
