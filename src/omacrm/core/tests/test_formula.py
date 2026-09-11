from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from omacrm.core.models import (
    Formula,
    Note,
    Notification,
    User,
    Webhook,
    WebhookQueueItem,
    Workflow,
)
from omacrm.core.services import formula as formula_service
from omacrm.core.services.formula import FormulaError, interpret
from omacrm.crm.models import Account, Lead, Opportunity, Task


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

    def test_string_and_date_helpers(self):
        lead = Lead(first_name="Helpers")
        interpret('account_name = upper("abc") + "-" + substring("hello", 1, 3)', lead)
        self.assertEqual(lead.account_name, "ABC-el")
        interpret('account_name = coalesce("", None, "fallback")', lead)
        self.assertEqual(lead.account_name, "fallback")
        interpret(
            'account_name = date_format(parse_date("2026-01-02"), "d/m/Y")', lead
        )
        self.assertEqual(lead.account_name, "02/01/2026")
        interpret('account_name = replace(lower(first_name), "help", "assist")', lead)
        self.assertEqual(lead.account_name, "assisters")

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

    def test_update_related_action(self):
        Workflow.objects.create(
            name="Lose all opportunities",
            entity_type="Account",
            event=Workflow.Event.UPDATE,
            actions=[
                {
                    "type": "update_related",
                    "relation": "opportunities",
                    "fields": {"stage": "Closed Lost"},
                }
            ],
        )
        account = Account.objects.create(name="Related Co")
        opportunity = Opportunity.objects.create(name="Deal", account=account)

        account.description = "trigger"
        account.save()

        opportunity.refresh_from_db()
        self.assertEqual(opportunity.stage, "Closed Lost")

    def test_update_related_validation(self):
        workflow = Workflow(
            name="Bad relation",
            entity_type="Account",
            event=Workflow.Event.UPDATE,
            actions=[
                {"type": "update_related", "relation": "nope", "fields": {"x": 1}}
            ],
        )
        with self.assertRaises(ValidationError):
            workflow.full_clean()

        workflow = Workflow(
            name="Bad related field",
            entity_type="Account",
            event=Workflow.Event.UPDATE,
            actions=[
                {
                    "type": "update_related",
                    "relation": "opportunities",
                    "fields": {"not_a_field": 1},
                }
            ],
        )
        with self.assertRaises(ValidationError):
            workflow.full_clean()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class WorkflowEmailTests(TestCase):
    def test_send_email_to_record_address(self):
        Workflow.objects.create(
            name="Welcome lead",
            entity_type="Lead",
            event=Workflow.Event.CREATE,
            actions=[
                {
                    "type": "send_email",
                    "to": "email_address",
                    "subject": "Hi {{ name }}",
                    "body": "<p>Hello {{ first_name }}</p>",
                }
            ],
        )
        lead = Lead.objects.create(
            first_name="Mail", last_name="Target", email_address="target@example.com"
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["target@example.com"])
        self.assertEqual(mail.outbox[0].subject, "Hi Mail Target")
        self.assertTrue(
            Note.objects.filter(parent_id=lead.pk, type=Note.Type.EMAIL).exists()
        )

    def test_send_email_to_literal_address(self):
        Workflow.objects.create(
            name="Notify ops",
            entity_type="Lead",
            event=Workflow.Event.CREATE,
            actions=[
                {
                    "type": "send_email",
                    "to": "ops@example.com",
                    "subject": "New lead",
                }
            ],
        )
        Lead.objects.create(first_name="No", last_name="Address")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ops@example.com"])

    def test_send_email_without_recipient_is_ignored(self):
        Workflow.objects.create(
            name="No recipient",
            entity_type="Lead",
            event=Workflow.Event.CREATE,
            actions=[{"type": "send_email", "subject": "x"}],
        )
        Lead.objects.create(first_name="No", last_name="Email")
        self.assertEqual(len(mail.outbox), 0)


class WorkflowWebhookTests(TestCase):
    def setUp(self):
        self.webhook = Webhook.objects.create(
            name="Lead hook",
            entity_type="Lead",
            event="update",
            url="https://example.com/hook",
        )

    def test_webhook_action_enqueues_payload(self):
        Workflow.objects.create(
            name="Hook flow",
            entity_type="Lead",
            event=Workflow.Event.CREATE,
            actions=[{"type": "webhook", "webhook_id": self.webhook.pk}],
        )
        Lead.objects.create(first_name="Web", last_name="Hook")

        item = WebhookQueueItem.objects.get(webhook=self.webhook)
        self.assertEqual(item.payload["entity_type"], "Lead")
        self.assertEqual(item.payload["data"]["last_name"], "Hook")

    def test_unknown_webhook_is_ignored(self):
        Workflow.objects.create(
            name="Bad hook",
            entity_type="Lead",
            event=Workflow.Event.CREATE,
            actions=[{"type": "webhook", "webhook_id": 999999}],
        )
        Lead.objects.create(first_name="No", last_name="Hook")
        self.assertFalse(WebhookQueueItem.objects.exists())

    def test_validation_requires_numeric_webhook_id(self):
        workflow = Workflow(
            name="Invalid hook",
            entity_type="Lead",
            event=Workflow.Event.CREATE,
            actions=[{"type": "webhook", "webhook_id": "abc"}],
        )
        with self.assertRaises(ValidationError):
            workflow.full_clean()
