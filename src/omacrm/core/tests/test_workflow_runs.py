from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from omacrm.core.models import Notification, User, Workflow, WorkflowRun
from omacrm.core.services import jobs, workflows
from omacrm.core.services.jobs import JobRunner, schedule
from omacrm.crm.models import Task


class WaitStepTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "wf-run", "wf-run@example.com", "pw"
        )

    def _rule(self, name, actions, event=Workflow.Event.CREATE):
        return Workflow.objects.create(
            name=name, entity_type="Task", event=event, actions=actions
        )

    def test_wait_duration_defers_and_resumes(self):
        rule = self._rule(
            "Late notify",
            [
                {"type": "wait", "duration": "1h"},
                {"type": "notify", "message": "Waited"},
            ],
        )
        Task.objects.create(name="Wait task", assigned_user=self.user)

        run = WorkflowRun.objects.get(workflow=rule)
        self.assertEqual(run.status, WorkflowRun.Status.WAITING)
        self.assertIsNotNone(run.execute_time)
        self.assertEqual(run.trace, [0])
        self.assertFalse(Notification.objects.filter(message="Waited").exists())

        self.assertEqual(workflows.resume_due_runs(), 0)
        resumed = workflows.resume_due_runs(
            now=timezone.now() + timedelta(hours=2)
        )
        self.assertEqual(resumed, 1)

        run.refresh_from_db()
        self.assertEqual(run.status, WorkflowRun.Status.SUCCESS)
        self.assertIsNone(run.execute_time)
        self.assertEqual(run.trace, [0, 1])
        self.assertTrue(
            Notification.objects.filter(
                user=self.user, message="Waited"
            ).exists()
        )

    def test_wait_until_date_field(self):
        rule = self._rule(
            "Due date wait",
            [
                {"type": "wait", "until_date_field": "date_end"},
                {"type": "notify", "message": "Due"},
            ],
        )
        due = timezone.now() + timedelta(days=2)
        Task.objects.create(name="Scheduled", assigned_user=self.user, date_end=due)

        run = WorkflowRun.objects.get(workflow=rule)
        self.assertEqual(run.status, WorkflowRun.Status.WAITING)
        self.assertLess(abs((run.execute_time - due).total_seconds()), 1)
        self.assertFalse(Notification.objects.filter(message="Due").exists())

        workflows.resume_due_runs(now=due + timedelta(seconds=1))
        self.assertTrue(Notification.objects.filter(message="Due").exists())

    def test_wait_until_date_field_in_the_past_does_not_wait(self):
        rule = self._rule(
            "Past date",
            [
                {"type": "wait", "until_date_field": "date_end"},
                {"type": "notify", "message": "Already due"},
            ],
        )
        Task.objects.create(
            name="Overdue",
            assigned_user=self.user,
            date_end=timezone.now() - timedelta(days=1),
        )
        self.assertFalse(WorkflowRun.objects.filter(workflow=rule).exists())
        self.assertTrue(Notification.objects.filter(message="Already due").exists())

    def test_wait_until_condition_polls_then_proceeds(self):
        rule = self._rule(
            "Wait for completion",
            [
                {
                    "type": "wait",
                    "until_condition": "status == 'Completed'",
                    "poll_interval": "10m",
                    "timeout": "1d",
                },
                {"type": "notify", "message": "Completed flow"},
            ],
        )
        task = Task.objects.create(
            name="In progress", status="Started", assigned_user=self.user
        )

        run = WorkflowRun.objects.get(workflow=rule)
        self.assertEqual(run.status, WorkflowRun.Status.WAITING)
        self.assertIsNotNone(run.wait_deadline)

        first_due = run.execute_time
        self.assertEqual(
            workflows.resume_due_runs(now=first_due + timedelta(seconds=1)), 1
        )
        run.refresh_from_db()
        self.assertEqual(run.status, WorkflowRun.Status.WAITING)
        self.assertGreater(run.execute_time, first_due)
        self.assertFalse(Notification.objects.filter(message="Completed flow").exists())

        task.status = "Completed"
        task.save()
        self.assertEqual(workflows.resume_due_runs(now=run.execute_time), 1)

        run.refresh_from_db()
        self.assertEqual(run.status, WorkflowRun.Status.SUCCESS)
        self.assertTrue(
            Notification.objects.filter(message="Completed flow").exists()
        )

    def test_wait_until_condition_times_out(self):
        rule = self._rule(
            "Never completed",
            [
                {
                    "type": "wait",
                    "until_condition": "status == 'Completed'",
                    "poll_interval": "1h",
                    "timeout": "2h",
                },
                {"type": "notify", "message": "Never"},
            ],
        )
        Task.objects.create(name="Stuck", status="Started", assigned_user=self.user)

        run = WorkflowRun.objects.get(workflow=rule)
        workflows.resume_due_runs(now=run.wait_deadline + timedelta(seconds=1))

        run.refresh_from_db()
        self.assertEqual(run.status, WorkflowRun.Status.FAILED)
        self.assertIn("timed out", run.last_error)
        self.assertFalse(Notification.objects.filter(message="Never").exists())

    def test_failed_run_can_be_retried(self):
        rule = self._rule(
            "Retryable",
            [
                {
                    "type": "wait",
                    "until_condition": "status == 'Completed'",
                    "poll_interval": "1h",
                    "timeout": "2h",
                },
                {"type": "notify", "message": "Eventually"},
            ],
        )
        task = Task.objects.create(
            name="Retry me", status="Started", assigned_user=self.user
        )

        run = WorkflowRun.objects.get(workflow=rule)
        workflows.resume_due_runs(now=run.wait_deadline + timedelta(seconds=1))
        run.refresh_from_db()
        self.assertEqual(run.status, WorkflowRun.Status.FAILED)

        task.status = "Completed"
        task.save()
        run.status = WorkflowRun.Status.RUNNING
        run.last_error = ""
        run.finished_at = None
        run.save(update_fields=["status", "last_error", "finished_at"])
        workflows.advance(run)

        run.refresh_from_db()
        self.assertEqual(run.status, WorkflowRun.Status.SUCCESS)
        self.assertTrue(Notification.objects.filter(message="Eventually").exists())

    def test_missing_record_cancels_run(self):
        rule = self._rule(
            "Missing record",
            [
                {"type": "wait", "duration": "1h"},
                {"type": "notify", "message": "Too late"},
            ],
        )
        task = Task.objects.create(name="Deleted", assigned_user=self.user)

        run = WorkflowRun.objects.get(workflow=rule)
        task.delete()
        workflows.resume_due_runs(now=timezone.now() + timedelta(hours=2))

        run.refresh_from_db()
        self.assertEqual(run.status, WorkflowRun.Status.CANCELLED)
        self.assertFalse(Notification.objects.filter(message="Too late").exists())


class BranchStepTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "wf-branch", "wf-branch@example.com", "pw"
        )

    def _rule(self, name, actions):
        return Workflow.objects.create(
            name=name, entity_type="Task", event=Workflow.Event.CREATE, actions=actions
        )

    def test_branch_routes_then_and_else(self):
        self._rule(
            "Completion branch",
            [
                {
                    "type": "branch",
                    "condition": "status == 'Completed'",
                    "then": [{"type": "notify", "message": "Done"}],
                    "else": [{"type": "notify", "message": "Open"}],
                }
            ],
        )
        Task.objects.create(name="Done", status="Completed", assigned_user=self.user)
        Task.objects.create(name="Open", status="Started", assigned_user=self.user)

        self.assertTrue(Notification.objects.filter(message="Done").exists())
        self.assertTrue(Notification.objects.filter(message="Open").exists())
        self.assertFalse(WorkflowRun.objects.exists())

    def test_branch_without_else_falls_through(self):
        self._rule(
            "No else",
            [
                {
                    "type": "branch",
                    "condition": "priority == 'High'",
                    "then": [{"type": "notify", "message": "High priority"}],
                },
                {"type": "notify", "message": "After branch"},
            ],
        )
        Task.objects.create(name="Routine", priority="Low", assigned_user=self.user)
        self.assertFalse(Notification.objects.filter(message="High priority").exists())
        self.assertTrue(Notification.objects.filter(message="After branch").exists())

    def test_nested_branch(self):
        self._rule(
            "Nested",
            [
                {
                    "type": "branch",
                    "condition": "status == 'Completed'",
                    "then": [
                        {
                            "type": "branch",
                            "condition": "priority == 'High'",
                            "then": [{"type": "notify", "message": "Urgent done"}],
                            "else": [{"type": "notify", "message": "Done"}],
                        }
                    ],
                }
            ],
        )
        Task.objects.create(
            name="Important",
            status="Completed",
            priority="High",
            assigned_user=self.user,
        )
        self.assertTrue(Notification.objects.filter(message="Urgent done").exists())
        self.assertFalse(Notification.objects.filter(message="Done").exists())

    def test_wait_inside_branch(self):
        self._rule(
            "Branch wait",
            [
                {
                    "type": "branch",
                    "condition": "status == 'Completed'",
                    "then": [
                        {"type": "wait", "duration": "1h"},
                        {"type": "notify", "message": "Then later"},
                    ],
                    "else": [{"type": "notify", "message": "Else now"}],
                }
            ],
        )
        Task.objects.create(name="Done", status="Completed", assigned_user=self.user)
        Task.objects.create(name="Open", status="Started", assigned_user=self.user)

        self.assertEqual(WorkflowRun.objects.count(), 1)
        self.assertTrue(Notification.objects.filter(message="Else now").exists())
        self.assertFalse(Notification.objects.filter(message="Then later").exists())

        workflows.resume_due_runs(now=timezone.now() + timedelta(hours=2))
        self.assertTrue(Notification.objects.filter(message="Then later").exists())


class RunJobTests(TestCase):
    def test_resume_job_is_registered_and_processes_runs(self):
        self.assertIsNotNone(jobs.get("core.resume_workflow_runs"))

        user = User.objects.create_user("wf-job", "wf-job@example.com", "pw")
        Workflow.objects.create(
            name="Job resume",
            entity_type="Task",
            event=Workflow.Event.CREATE,
            actions=[
                {"type": "wait", "duration": "1h"},
                {"type": "notify", "message": "Job ran"},
            ],
        )
        Task.objects.create(name="Queued", assigned_user=user)
        run = WorkflowRun.objects.get()

        schedule("core.resume_workflow_runs")
        run.execute_time = timezone.now()
        run.save(update_fields=["execute_time"])
        JobRunner.run_pending(limit=10)

        run.refresh_from_db()
        self.assertEqual(run.status, WorkflowRun.Status.SUCCESS)
        self.assertTrue(Notification.objects.filter(message="Job ran").exists())


class WorkflowRunAdminTests(TestCase):
    def test_changelist_renders(self):
        user = User.objects.create_superuser(
            "wf-admin", "wf-admin@example.com", "pw"
        )
        self.client.force_login(user)
        response = self.client.get(reverse("admin:core_workflowrun_changelist"))
        self.assertEqual(response.status_code, 200)


class WorkflowFlowViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            "wf-flow", "wf-flow@example.com", "pw"
        )
        self.client.force_login(self.user)
        self.rule = Workflow.objects.create(
            name="Flow view",
            entity_type="Task",
            event=Workflow.Event.CREATE,
            actions=[
                {"type": "notify", "message": "start"},
                {"type": "wait", "duration": "1h"},
                {
                    "type": "branch",
                    "condition": "status == 'Completed'",
                    "then": [{"type": "notify", "message": "done"}],
                    "else": [{"type": "notify", "message": "open"}],
                },
            ],
        )
        Task.objects.create(name="Flow task", assigned_user=self.user)

    def test_workflow_change_shows_flow_preview(self):
        response = self.client.get(
            reverse("admin:core_workflow_change", args=[self.rule.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Flow")
        self.assertContains(response, "Wait")
        self.assertContains(response, "Branch")
        self.assertContains(response, "status == &#x27;Completed&#x27;")

    def test_workflow_run_change_shows_state(self):
        run = WorkflowRun.objects.get(workflow=self.rule)
        response = self.client.get(
            reverse("admin:core_workflowrun_change", args=[run.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Flow")
        self.assertContains(response, "check_circle")
        self.assertContains(response, "schedule")
        self.assertContains(response, "due")


class ActionValidationTests(TestCase):
    def _validate(self, actions):
        workflow = Workflow(
            name="Validation target",
            entity_type="Task",
            event=Workflow.Event.CREATE,
            actions=actions,
        )
        with self.assertRaises(ValidationError):
            workflow.full_clean()

    def test_wait_requires_exactly_one_mode(self):
        self._validate([{"type": "wait"}])
        self._validate([{"type": "wait", "duration": "1h", "until_condition": "x"}])

    def test_wait_duration_format(self):
        self._validate([{"type": "wait", "duration": "soon"}])

    def test_wait_unknown_date_field(self):
        self._validate([{"type": "wait", "until_date_field": "nope"}])

    def test_wait_unknown_poll_interval(self):
        self._validate(
            [
                {
                    "type": "wait",
                    "until_condition": "status == 'Completed'",
                    "poll_interval": "often",
                }
            ]
        )

    def test_wait_accepts_metadata_field(self):
        workflow = Workflow(
            name="Metadata field wait",
            entity_type="Task",
            event=Workflow.Event.CREATE,
            actions=[
                {"type": "wait", "until_date_field": "date_end"},
                {"type": "notify", "message": "x"},
            ],
        )
        workflow.full_clean()

    def test_branch_requires_condition_and_then(self):
        self._validate([{"type": "branch", "then": [{"type": "notify"}]}])
        self._validate(
            [
                {
                    "type": "branch",
                    "condition": "status == 'Completed'",
                    "then": [],
                }
            ]
        )

    def test_branch_invalid_condition(self):
        self._validate(
            [
                {
                    "type": "branch",
                    "condition": "status ==",
                    "then": [{"type": "notify"}],
                }
            ]
        )

    def test_nested_action_is_validated(self):
        self._validate(
            [
                {
                    "type": "branch",
                    "condition": "status == 'Completed'",
                    "then": [{"type": "set_field", "field": "nope", "value": 1}],
                }
            ]
        )

    def test_branch_depth_is_limited(self):
        body = [{"type": "notify", "message": "deep"}]
        for _ in range(7):
            body = [
                {
                    "type": "branch",
                    "condition": "status == 'Completed'",
                    "then": body,
                }
            ]
        self._validate(body)
