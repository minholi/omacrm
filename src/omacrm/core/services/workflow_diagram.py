"""Read-only visualization of compiled workflow programs.

``core/services/workflows.py`` compiles nested actions into a flat jump-based
program. This module turns that program into a nested display tree and
annotates it with a run's execution state (from its ``trace`` and ``cursor``),
so the admin can draw the flow without executing anything.
"""

STATE_PENDING = "pending"
STATE_DONE = "done"
STATE_WAITING = "waiting"
STATE_FAILED = "failed"
STATE_CANCELLED = "cancelled"
STATE_ACTIVE = "active"

_STATE_STYLES = {
    STATE_DONE: ("check_circle", "text-primary-600"),
    STATE_ACTIVE: ("radio_button_checked", "text-primary-500"),
    STATE_WAITING: ("schedule", "text-primary-500"),
    STATE_FAILED: ("error", "text-red-600"),
    STATE_CANCELLED: ("block", "text-base-400"),
    STATE_PENDING: ("radio_button_unchecked", "text-base-400"),
}

ACTION_LABELS = {
    "set_field": "Set field",
    "notify": "Notify assigned user",
    "create_record": "Create record",
    "send_email": "Send email",
    "webhook": "Call webhook",
    "update_related": "Update related records",
}


def format_duration(seconds) -> str:
    seconds = int(seconds or 0)
    for unit, size in (("w", 604800), ("d", 86400), ("h", 3600), ("m", 60)):
        if seconds and seconds % size == 0:
            return f"{seconds // size}{unit}"
    return f"{seconds}s"


def _action_display(action: dict) -> tuple[str, str]:
    action_type = str(action.get("type") or "")
    label = ACTION_LABELS.get(action_type, action_type or "Action")
    if action_type == "set_field":
        return label, f"{action.get('field')} = {action.get('value')}"
    if action_type == "notify":
        return label, str(action.get("message") or "")
    if action_type == "send_email":
        return label, str(action.get("subject") or action.get("to") or "")
    if action_type == "create_record":
        return label, str(action.get("entity_type") or "")
    if action_type == "webhook":
        return label, str(action.get("webhook_id") or "")
    if action_type == "update_related":
        fields = ", ".join((action.get("fields") or {}).keys())
        return label, f"{action.get('relation')} ({fields})" if fields else str(
            action.get("relation") or ""
        )
    return label, ""


def _wait_display(step: dict) -> tuple[str, str]:
    mode = step.get("mode")
    if mode == "duration":
        return "Wait", format_duration(step.get("seconds"))
    if mode == "until_date":
        return "Wait until", str(step.get("field") or "")
    detail = str(step.get("condition") or "")
    poll = format_duration(step.get("poll_seconds"))
    timeout = format_duration(step.get("timeout_seconds"))
    if detail:
        detail = f"{detail} (poll {poll}, timeout {timeout})"
    return "Wait until", detail


class _RunState:
    """Execution state of a program for one run."""

    def __init__(self, run, program):
        self.run = run
        self.program = program
        self.trace = set(run.trace or []) if run is not None else set()
        self.cursor = run.cursor if run is not None else None
        self.status = run.status if run is not None else ""
        self.waiting_index = self._waiting_index()

    def _waiting_index(self):
        """The wait step a paused run is sitting on.

        A duration/date wait advances the cursor past itself, while a
        condition wait keeps the cursor on the step, so resolve the paused
        wait from the most recently executed wait in the trace.
        """

        if self.run is None or self.status != "waiting":
            return None
        for index in reversed(self.run.trace or []):
            if 0 <= index < len(self.program) and self.program[index].get(
                "op"
            ) == "wait":
                return index
        return self.cursor

    def state(self, index: int) -> str:
        if self.run is None:
            return STATE_PENDING
        if self.status == "waiting":
            if index == self.waiting_index:
                return STATE_WAITING
            if index == self.cursor:
                return STATE_PENDING
        if self.status == "failed" and index == self.cursor:
            return STATE_FAILED
        if self.status == "cancelled" and index == self.cursor:
            return STATE_CANCELLED
        if index in self.trace:
            return STATE_DONE
        return STATE_PENDING


def _styled(node: dict) -> dict:
    icon, css = _STATE_STYLES.get(node.get("state"), _STATE_STYLES[STATE_PENDING])
    node["state_icon"] = icon
    node["state_class"] = css
    return node


def _nodes(program, start: int, stop: int, state: _RunState) -> list[dict]:
    nodes = []
    start = max(0, start)
    stop = min(len(program), max(start, stop))
    index = start

    while index < stop:
        step = program[index]
        op = step.get("op")

        if op == "branch":
            then_start = int(step.get("then", index + 1))
            else_start = step.get("else")
            end = int(step.get("end", stop))
            if else_start is not None:
                then_nodes = _nodes(program, then_start, int(else_start) - 1, state)
                else_nodes = _nodes(program, int(else_start), end, state)
            else:
                then_nodes = _nodes(program, then_start, end, state)
                else_nodes = []
            nodes.append(
                _styled(
                    {
                        "kind": "branch",
                        "index": index,
                        "condition": str(step.get("condition") or ""),
                        "state": _branch_state(state, index, then_nodes, else_nodes),
                        "then": then_nodes,
                        "else": else_nodes,
                    }
                )
            )
            index = end

        elif op == "wait":
            label, detail = _wait_display(step)
            node_state = state.state(index)
            nodes.append(
                _styled(
                    {
                        "kind": "wait",
                        "index": index,
                        "state": node_state,
                        "label": label,
                        "detail": detail,
                        "due": state.run.execute_time
                        if node_state == STATE_WAITING and state.run is not None
                        else None,
                        "deadline": state.run.wait_deadline
                        if node_state == STATE_WAITING and state.run is not None
                        else None,
                    }
                )
            )
            index += 1

        elif op == "jump":
            index += 1

        else:
            label, detail = _action_display(step.get("action") or {})
            nodes.append(
                _styled(
                    {
                        "kind": "action",
                        "index": index,
                        "state": state.state(index),
                        "type": (step.get("action") or {}).get("type") or "",
                        "label": label,
                        "detail": detail,
                    }
                )
            )
            index += 1

    return nodes


def _branch_state(state: _RunState, index: int, then_nodes, else_nodes) -> str:
    own = state.state(index)
    if own in {STATE_FAILED, STATE_CANCELLED}:
        return own
    child_states = {node.get("state") for node in then_nodes + else_nodes}
    if child_states & {STATE_WAITING, STATE_FAILED}:
        return STATE_ACTIVE
    if own in {STATE_DONE, STATE_WAITING}:
        return own
    if STATE_DONE in child_states:
        return STATE_DONE
    return STATE_PENDING


def build_flow(program, run=None) -> list[dict]:
    """Return display nodes for a compiled program.

    ``run`` may be a saved or unsaved ``WorkflowRun``; without it every step
    is pending (rule preview).
    """

    program = list(program or [])
    return _nodes(program, 0, len(program), _RunState(run, program))
