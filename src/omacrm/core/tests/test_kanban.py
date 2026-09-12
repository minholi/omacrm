from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from omacrm.core.metadata.registry import registry
from omacrm.core.models import (
    CustomEntity,
    CustomField,
    DynamicRecord,
    KanbanOrder,
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


class KanbanOrderTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "kanban-order", "kanban-order@example.com", "pw"
        )
        self.other = User.objects.create_user(
            "kanban-other", "kanban-other@example.com", "pw", is_staff=True
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
        self.proxy = custom_entities.get_proxy("Project")
        self.addCleanup(registry.invalidate)
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        DynamicRecord.objects.filter(entity_type="Project").delete()
        CustomField.objects.filter(entity_type="Project").delete()
        custom_entities.unregister(self.entity)
        if self.entity.pk:
            self.entity.delete()
        registry.invalidate()

    def _record(self, name, status="Active", assigned_user=None):
        return self.proxy.objects.create(
            entity_type="Project",
            name=name,
            assigned_user=assigned_user,
            custom_data={"status": status},
        )

    def _column(self, board, value):
        for column in board["columns"]:
            if column["value"] == value:
                return [record.pk for record in column["records"]]
        return []

    def _order_url(self):
        return reverse("kanban_order", kwargs={"entity_type": "Project"})

    def test_reorder_persists_and_board_returns_stored_order(self):
        a = self._record("Alpha")
        b = self._record("Bravo")
        c = self._record("Charlie")
        kanban.reorder(self.admin, "Project", "Active", [c.pk, a.pk, b.pk])
        board = kanban.board("Project", self.admin)
        self.assertEqual(self._column(board, "Active"), [c.pk, a.pk, b.pk])
        rows = list(
            KanbanOrder.objects.filter(user=self.admin)
            .order_by("order")
            .values_list("entity_id", "group", "order")
        )
        self.assertEqual(
            rows,
            [(c.pk, "Active", 0), (a.pk, "Active", 1), (b.pk, "Active", 2)],
        )

    def test_order_is_per_user(self):
        a = self._record("Alpha")
        b = self._record("Bravo")
        untouched = self._column(kanban.board("Project", self.other), "Active")
        kanban.reorder(self.admin, "Project", "Active", [b.pk, a.pk])
        self.assertEqual(
            self._column(kanban.board("Project", self.admin), "Active"),
            [b.pk, a.pk],
        )
        self.assertEqual(
            self._column(kanban.board("Project", self.other), "Active"),
            untouched,
        )
        self.assertFalse(KanbanOrder.objects.filter(user=self.other).exists())

    def test_cards_without_stored_order_follow_ordered_ones(self):
        for name in ("Alpha", "Bravo", "Charlie"):
            self._record(name)
        before = self._column(kanban.board("Project", self.admin), "Active")
        last = before[-1]
        kanban.reorder(self.admin, "Project", "Active", [last])
        after = self._column(kanban.board("Project", self.admin), "Active")
        self.assertEqual(after[0], last)
        self.assertEqual(after[1:], [pk for pk in before if pk != last])

    def test_no_stored_order_keeps_metadata_ordering(self):
        for name in ("Alpha", "Bravo", "Charlie"):
            self._record(name)
        self.assertFalse(KanbanOrder.objects.exists())
        board = kanban.board("Project", self.admin)
        ordering = registry.get("Project").ordering or ["-created_at"]
        expected = list(
            self.proxy.objects.filter(entity_type="Project")
            .order_by(*ordering)
            .values_list("pk", flat=True)
        )
        self.assertEqual(self._column(board, "Active"), expected)

    def test_move_to_another_column_clears_stored_order(self):
        a = self._record("Alpha")
        b = self._record("Bravo")
        done = self._record("Done Record", status="Done")
        kanban.reorder(self.admin, "Project", "Active", [b.pk, a.pk])
        kanban.reorder(self.other, "Project", "Active", [b.pk, a.pk])
        kanban.reorder(self.admin, "Project", "Done", [done.pk])
        kanban.move_record(a, "Project", "status", "Done")
        self.assertFalse(KanbanOrder.objects.filter(entity_id=a.pk).exists())
        board = kanban.board("Project", self.admin)
        self.assertEqual(self._column(board, "Active"), [b.pk])
        self.assertEqual(self._column(board, "Done"), [done.pk, a.pk])

    def test_order_endpoint_persists_list(self):
        a = self._record("Alpha")
        b = self._record("Bravo")
        c = self._record("Charlie")
        response = self.client.post(
            self._order_url(),
            data={"group": "Active", "ids": [c.pk, b.pk, a.pk]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            self._column(kanban.board("Project", self.admin), "Active"),
            [c.pk, b.pk, a.pk],
        )

    def test_order_endpoint_requires_authentication(self):
        self._record("Alpha")
        self.client.logout()
        response = self.client.post(
            self._order_url(),
            data={"group": "Active", "ids": []},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(KanbanOrder.objects.exists())

    def test_order_endpoint_requires_csrf(self):
        record = self._record("Alpha")
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        response = csrf_client.post(
            self._order_url(),
            data={"group": "Active", "ids": [record.pk]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(KanbanOrder.objects.exists())

    def test_order_endpoint_rejects_records_outside_the_column(self):
        active = self._record("Alpha")
        done = self._record("Bravo", status="Done")
        response = self.client.post(
            self._order_url(),
            data={"group": "Active", "ids": [active.pk, done.pk]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(KanbanOrder.objects.exists())

    def test_order_endpoint_rejects_invisible_records(self):
        role = Role.objects.create(
            name="Kanban own", data={"Project": {"read": "own", "edit": "no"}}
        )
        staff = User.objects.create_user(
            "kanban-own", "kanban-own@example.com", "pw", is_staff=True
        )
        staff.roles.add(role)
        visible = self._record("Visible", assigned_user=staff)
        hidden = self._record("Hidden", assigned_user=self.admin)
        self.client.force_login(staff)
        response = self.client.post(
            self._order_url(),
            data={"group": "Active", "ids": [visible.pk, hidden.pk]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(KanbanOrder.objects.exists())

    def test_order_endpoint_rejects_bad_payload(self):
        self._record("Alpha")
        response = self.client.post(
            self._order_url(), data=b"{", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            self._order_url(),
            data={"group": "Active", "ids": "1"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            self._order_url(),
            data={"group": "Nope", "ids": []},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            self._order_url(),
            data={"group": "Active", "ids": [999999]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.get(self._order_url())
        self.assertEqual(response.status_code, 405)
        self.assertFalse(KanbanOrder.objects.exists())

    def test_full_column_reorder_is_a_constant_number_of_queries(self):
        records = [self._record(f"Record {index}") for index in range(12)]
        ids = [record.pk for record in records]
        kanban.kanban_config("Project")
        with CaptureQueriesContext(connection) as first:
            kanban.reorder(self.admin, "Project", "Active", ids)
        more = [self._record(f"Extra {index}") for index in range(12)]
        ids += [record.pk for record in more]
        with CaptureQueriesContext(connection) as second:
            kanban.reorder(self.admin, "Project", "Active", ids)
        self.assertLess(len(first.captured_queries), len(records))
        self.assertEqual(len(first.captured_queries), len(second.captured_queries))
