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
from omacrm.core.services import custom_entities, kanban
from omacrm.crm.models import Opportunity, Task

STATUS_CHOICES = [["Active", "Active"], ["On Hold", "On Hold"], ["Done", "Done"]]


class KanbanConfigTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "kanban-admin", "kanban@example.com", "pw"
        )
        self.client.force_login(self.admin)
        self.entity = CustomEntity.objects.create(
            name="Project", label="Project", label_plural="Projects"
        )
        CustomField.objects.create(
            entity_type="Project",
            name="status",
            label="Status",
            field_type="enum",
            params={"choices": STATUS_CHOICES},
        )
        self.entity.status_field = "status"
        self.entity.save()
        registry.invalidate()
        self.addCleanup(registry.invalidate)
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        DynamicRecord.objects.filter(entity_type="Project").delete()
        CustomField.objects.filter(entity_type="Project").delete()
        custom_entities.unregister(self.entity)
        if self.entity.pk:
            self.entity.delete()
        registry.invalidate()

    def test_custom_entity_config(self):
        config = kanban.kanban_config("Project")
        self.assertIsNotNone(config)
        self.assertEqual(config["field"], "status")
        self.assertEqual(config["choices"], [("Active", "Active"), ("On Hold", "On Hold"), ("Done", "Done")])

    def test_builtin_entity_config(self):
        opportunity = kanban.kanban_config("Opportunity")
        self.assertIsNotNone(opportunity)
        self.assertEqual(opportunity["field"], "stage")
        self.assertIn(("Proposal", "Proposal"), opportunity["choices"])

        task = kanban.kanban_config("Task")
        self.assertEqual(task["field"], "status")

    def test_custom_entity_without_field_has_no_config(self):
        self.entity.status_field = ""
        self.entity.save()
        registry.invalidate()
        self.assertIsNone(kanban.kanban_config("Project"))

    def test_board_groups_records(self):
        proxy = custom_entities.get_proxy("Project")
        proxy.objects.create(
            entity_type="Project", name="Apollo", custom_data={"status": "Active"}
        )
        proxy.objects.create(
            entity_type="Project", name="Zeus", custom_data={"status": "Done"}
        )
        board = kanban.board("Project", self.admin)
        by_value = {column["value"]: column["label"] for column in board["columns"]}
        self.assertIn("Active", by_value)
        counts = {
            column["value"]: len(column["records"])
            for column in board["columns"]
        }
        self.assertEqual(counts["Active"], 1)
        self.assertEqual(counts["Done"], 1)

    def test_move_record_updates_status(self):
        record = custom_entities.get_proxy("Project").objects.create(
            entity_type="Project", name="Apollo", custom_data={"status": "Active"}
        )
        kanban.move_record(record, "Project", "status", "Done")
        record.refresh_from_db()
        self.assertEqual(record.custom_data["status"], "Done")
        with self.assertRaises(ValueError):
            kanban.move_record(record, "Project", "status", "Nope")


class KanbanViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "kanban-view", "kanban-view@example.com", "pw"
        )
        self.client.force_login(self.admin)
        self.entity = CustomEntity.objects.create(
            name="Project", label="Project", label_plural="Projects"
        )
        CustomField.objects.create(
            entity_type="Project",
            name="status",
            label="Status",
            field_type="enum",
            params={"choices": STATUS_CHOICES},
        )
        self.entity.status_field = "status"
        self.entity.save()
        registry.invalidate()
        self.record = custom_entities.get_proxy("Project").objects.create(
            entity_type="Project",
            name="Apollo",
            assigned_user=self.admin,
            custom_data={"status": "Active"},
        )
        self.addCleanup(registry.invalidate)
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        DynamicRecord.objects.filter(entity_type="Project").delete()
        CustomField.objects.filter(entity_type="Project").delete()
        custom_entities.unregister(self.entity)
        if self.entity.pk:
            self.entity.delete()
        registry.invalidate()

    def test_board_renders_cards_and_columns(self):
        response = self.client.get(
            reverse("kanban_board", kwargs={"entity_type": "Project"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Apollo")
        self.assertContains(response, "On Hold")
        self.assertContains(response, reverse("kanban_move", kwargs={"entity_type": "Project"}))

    def test_board_404_for_entity_without_kanban(self):
        self.assertEqual(
            self.client.get(
                reverse("kanban_board", kwargs={"entity_type": "Account"})
            ).status_code,
            404,
        )

    def test_move_endpoint_updates_record(self):
        response = self.client.post(
            reverse("kanban_move", kwargs={"entity_type": "Project"}),
            data={"pk": self.record.pk, "value": "Done"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.record.refresh_from_db()
        self.assertEqual(self.record.custom_data["status"], "Done")

    def test_move_endpoint_rejects_unknown_value(self):
        response = self.client.post(
            reverse("kanban_move", kwargs={"entity_type": "Project"}),
            data={"pk": self.record.pk, "value": "Nope"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_move_endpoint_requires_edit(self):
        role = Role.objects.create(
            name="Read only", data={"Project": {"read": "all", "edit": "no"}}
        )
        staff = User.objects.create_user(
            "kanban-read", "kanban-read@example.com", "pw", is_staff=True
        )
        staff.roles.add(role)
        self.client.force_login(staff)
        response = self.client.post(
            reverse("kanban_move", kwargs={"entity_type": "Project"}),
            data={"pk": self.record.pk, "value": "Done"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_changelist_shows_kanban_link(self):
        response = self.client.get(reverse("admin:core_project_changelist"))
        self.assertContains(response, "Kanban view")
        self.assertContains(
            response, reverse("kanban_board", kwargs={"entity_type": "Project"})
        )

    def test_builtin_kanban_board_renders(self):
        Opportunity.objects.create(name="Deal", stage="Proposal")
        response = self.client.get(
            reverse("kanban_board", kwargs={"entity_type": "Opportunity"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Deal")
        Task.objects.create(name="Follow up", status="Started")
        response = self.client.get(
            reverse("kanban_board", kwargs={"entity_type": "Task"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Follow up")
