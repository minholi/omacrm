from django.core.exceptions import ValidationError
from django.test import TestCase

from omacrm.core.models import Formula, Notification, User, Workflow
from omacrm.core.services import formula as formula_service
from omacrm.core.services.formula import FormulaError, interpret
from omacrm.crm.models import Account, Lead, Task


class FormulaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("formula", "formula@example.com", "pw")
        self.addCleanup(formula_service.invalidate_formula_cache)

    def test_before_save_assignment_persists(self):
        Formula.objects.create(
            entity_type="Lead",
            event=Formula.Event.BEFORE_SAVE,
            script='account_name = "Formula Co"',
        )
        lead = Lead.objects.create(first_name="F", last_name="Formula")
        lead.refresh_from_db()
        self.assertEqual(lead.account_name, "Formula Co")

    def test_after_save_update_function(self):
        Formula.objects.create(
            entity_type="Lead",
            event=Formula.Event.AFTER_SAVE,
            script='update("phone_number", "555-0100")',
        )
        lead = Lead.objects.create(first_name="F", last_name="After")
        lead.refresh_from_db()
        self.assertEqual(lead.phone_number, "555-0100")

    def test_custom_field_assignment(self):
        Formula.objects.create(
            entity_type="Lead",
            event=Formula.Event.BEFORE_SAVE,
            script='custom.score = len(last_name) * 10\ncustom.label = "hot"',
        )
        lead = Lead.objects.create(first_name="F", last_name="Four")
        lead.refresh_from_db()
        self.assertEqual(lead.custom_data["score"], 40)
        self.assertEqual(lead.custom_data["label"], "hot")

    def test_notify_function(self):
        Formula.objects.create(
            entity_type="Task",
            event=Formula.Event.AFTER_SAVE,
            script='notify("Task created")',
        )
        task = Task.objects.create(name="Notify task", assigned_user=self.user)
        self.assertTrue(
            Notification.objects.filter(user=self.user, message="Task created").exists()
        )

    def test_sandbox_blocks_dangerous_expressions(self):
        instance = Account()
        for expression in (
            "__import__('os')",
            "record._meta",
            "open('/etc/passwd')",
            "eval('1+1')",
        ):
            with self.assertRaises(FormulaError, msg=expression):
                interpret(expression, instance)

    def test_arithmetic_and_conditionals(self):
        account = Account(name="Arithmetic")
        interpret('description = "value: " + str(1 + 2 * 3)', account)
        self.assertEqual(account.description, "value: 7")
        interpret('description = "yes" if len(name) > 3 else "no"', account)
        self.assertEqual(account.description, "yes")

    def test_validation_rejects_bad_scripts(self):
        formula = Formula(
            entity_type="Lead", event=Formula.Event.BEFORE_SAVE, script="account_name = ("
        )
        with self.assertRaises(ValidationError):
            formula.full_clean()

        formula = Formula(
            entity_type="NotAnEntity", event=Formula.Event.BEFORE_SAVE, script=""
        )
        with self.assertRaises(ValidationError):
            formula.full_clean()


class WorkflowTests(TestCase):
    def test_set_field_action_with_condition(self):
        Workflow.objects.create(
            name="Complete tasks",
            entity_type="Task",
            event=Workflow.Event.CREATE,
            condition="status == 'Completed'",
            actions=[{"type": "set_field", "field": "priority", "value": "High"}],
        )
        task = Task.objects.create(name="Completed task", status="Completed")
        task.refresh_from_db()
        self.assertEqual(task.priority, "High")

    def test_condition_gates_action(self):
        Workflow.objects.create(
            name="Not started only",
            entity_type="Task",
            event=Workflow.Event.CREATE,
            condition="status == 'Not Started'",
            actions=[{"type": "set_field", "field": "priority", "value": "Urgent"}],
        )
        task = Task.objects.create(name="Other", status="Started")
        task.refresh_from_db()
        self.assertEqual(task.priority, "Normal")

    def test_notify_action(self):
        user = User.objects.create_user("wfuser", "wf@example.com", "pw")
        Workflow.objects.create(
            name="Notify",
            entity_type="Task",
            event=Workflow.Event.CREATE,
            condition="",
            actions=[{"type": "notify", "message": "Workflow ran"}],
        )
        Task.objects.create(name="Notify task", assigned_user=user)
        self.assertTrue(
            Notification.objects.filter(user=user, message="Workflow ran").exists()
        )

    def test_create_record_action(self):
        Workflow.objects.create(
            name="Create task",
            entity_type="Lead",
            event=Workflow.Event.CREATE,
            condition="",
            actions=[
                {
                    "type": "create_record",
                    "entity_type": "Task",
                    "values": {"name": "Follow up lead"},
                }
            ],
        )
        Lead.objects.create(first_name="Trigger", last_name="Lead")
        self.assertTrue(Task.objects.filter(name="Follow up lead").exists())

    def test_validation_rejects_unknown_action_field(self):
        workflow = Workflow(
            name="Bad",
            entity_type="Task",
            event=Workflow.Event.CREATE,
            actions=[{"type": "set_field", "field": "nope", "value": 1}],
        )
        with self.assertRaises(ValidationError):
            workflow.full_clean()
