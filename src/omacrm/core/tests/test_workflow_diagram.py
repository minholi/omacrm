from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from omacrm.core.models import WorkflowRun
from omacrm.core.services.workflow_diagram import (
    STATE_ACTIVE,
    STATE_DONE,
    STATE_FAILED,
    STATE_PENDING,
    STATE_WAITING,
    build_flow,
    format_duration,
)
from omacrm.core.services.workflows import compile_actions


class DiagramStructureTests(TestCase):
    def test_branch_then_else_structure(self):
        program = compile_actions(
            [
                {
                    "type": "branch",
                    "condition": "stage == 'Proposal'",
                    "then": [{"type": "notify", "message": "still open"}],
                    "else": [
                        {"type": "set_field", "field": "stage", "value": "Lost"}
                    ],
                }
            ]
        )
        nodes = build_flow(program)
        self.assertEqual(len(nodes), 1)
        branch = nodes[0]
        self.assertEqual(branch["kind"], "branch")
        self.assertEqual(branch["condition"], "stage == 'Proposal'")
        self.assertEqual([node["kind"] for node in branch["then"]], ["action"])
        self.assertEqual([node["kind"] for node in branch["else"]], ["action"])
        self.assertEqual(
            {node["state"] for node in branch["then"] + branch["else"]},
            {STATE_PENDING},
        )

    def test_wait_descriptions(self):
        program = compile_actions(
            [
                {"type": "wait", "duration": "3d"},
                {"type": "wait", "until_date_field": "date_end"},
                {
                    "type": "wait",
                    "until_condition": "status == 'Completed'",
                    "poll_interval": "1h",
                    "timeout": "30d",
                },
            ]
        )
        nodes = build_flow(program)
        self.assertEqual(
            (nodes[0]["label"], nodes[0]["detail"]), ("Wait", "3d")
        )
        self.assertEqual(
            (nodes[1]["label"], nodes[1]["detail"]),
            ("Wait until", "date_end"),
        )
        self.assertEqual(nodes[2]["label"], "Wait until")
        self.assertIn("status == 'Completed'", nodes[2]["detail"])
        self.assertIn("poll 1h", nodes[2]["detail"])
        self.assertIn("timeout 30d", nodes[2]["detail"])

    def test_action_descriptions(self):
        program = compile_actions(
            [
                {"type": "notify", "message": "hello"},
                {"type": "create_record", "entity_type": "Task", "values": {}},
                {"type": "mystery", "x": 1},
            ]
        )
        nodes = build_flow(program)
        self.assertEqual(nodes[0]["label"], "Notify assigned user")
        self.assertEqual(nodes[0]["detail"], "hello")
        self.assertEqual(nodes[1]["detail"], "Task")
        self.assertEqual(nodes[2]["type"], "mystery")
        self.assertEqual(nodes[2]["label"], "mystery")

    def test_format_duration(self):
        self.assertEqual(format_duration(3 * 86400), "3d")
        self.assertEqual(format_duration(3600), "1h")
        self.assertEqual(format_duration(90), "90s")
        self.assertEqual(format_duration(None), "0s")


class DiagramStateTests(TestCase):
    def _program(self):
        return compile_actions(
            [
                {"type": "notify", "message": "first"},
                {"type": "wait", "duration": "1h"},
                {
                    "type": "branch",
                    "condition": "x == 1",
                    "then": [{"type": "notify", "message": "a"}],
                    "else": [{"type": "notify", "message": "b"}],
                },
            ]
        )

    def test_pending_without_run(self):
        nodes = build_flow(self._program())
        self.assertEqual(nodes[0]["state"], STATE_PENDING)
        self.assertEqual(nodes[0]["state_icon"], "radio_button_unchecked")

    def test_waiting_run_marks_processed_and_waiting(self):
        due = timezone.now() + timedelta(hours=1)
        program = self._program()
        run = WorkflowRun(
            program=program,
            trace=[0, 1],
            cursor=2,
            status=WorkflowRun.Status.WAITING,
            execute_time=due,
        )
        nodes = build_flow(program, run)
        self.assertEqual(nodes[0]["state"], STATE_DONE)
        self.assertEqual(nodes[1]["state"], STATE_WAITING)
        self.assertEqual(nodes[1]["due"], due)
        self.assertEqual(nodes[1]["state_icon"], "schedule")
        self.assertEqual(nodes[2]["state"], STATE_PENDING)
        self.assertEqual(nodes[2]["then"][0]["state"], STATE_PENDING)

    def test_resumed_branch_path_marked_done(self):
        program = self._program()
        run = WorkflowRun(
            program=program,
            trace=[0, 1, 2, 3, 4],
            cursor=6,
            status=WorkflowRun.Status.SUCCESS,
        )
        nodes = build_flow(program, run)
        branch = nodes[2]
        self.assertEqual(branch["state"], STATE_DONE)
        self.assertEqual(branch["then"][0]["state"], STATE_DONE)
        self.assertEqual(branch["else"][0]["state"], STATE_PENDING)

    def test_failed_step_marked(self):
        program = self._program()
        run = WorkflowRun(
            program=program,
            trace=[0],
            cursor=1,
            status=WorkflowRun.Status.FAILED,
        )
        nodes = build_flow(program, run)
        self.assertEqual(nodes[1]["state"], STATE_FAILED)
        self.assertEqual(nodes[1]["state_icon"], "error")

    def test_branch_with_waiting_descendant_is_active(self):
        program = compile_actions(
            [
                {
                    "type": "branch",
                    "condition": "x == 1",
                    "then": [{"type": "wait", "duration": "1h"}],
                    "else": [{"type": "notify", "message": "b"}],
                }
            ]
        )
        run = WorkflowRun(
            program=program,
            trace=[0, 1],
            cursor=2,
            status=WorkflowRun.Status.WAITING,
            execute_time=timezone.now() + timedelta(hours=1),
        )
        nodes = build_flow(program, run)
        self.assertEqual(nodes[0]["state"], STATE_ACTIVE)
        self.assertEqual(nodes[0]["then"][0]["state"], STATE_WAITING)
        self.assertEqual(nodes[0]["else"][0]["state"], STATE_PENDING)
