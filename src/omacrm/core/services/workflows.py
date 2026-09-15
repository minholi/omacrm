"""Workflow automation: trigger → optional condition → steps.

Steps can be immediate actions, ``wait`` steps (a duration, a date field or a
condition) and ``branch`` steps with ``then``/``else`` bodies. A rule that
reaches a wait is persisted as a :class:`~omacrm.core.models.WorkflowRun`
holding the compiled program and cursor; the ``core.resume_workflow_runs`` job
resumes due runs. Rules without waits execute entirely inline and leave no
rows behind.
"""

import contextvars
import logging
import re
from datetime import date, datetime, time, timedelta

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from omacrm.core.metadata.registry import registry
from omacrm.core.services.formula import (
    FormulaError,
    build_context,
    evaluate,
    validate_expression,
)

logger = logging.getLogger(__name__)

_running = contextvars.ContextVar("omacrm_workflow_running", default=False)

DURATION_RE = re.compile(r"^(\d+)([mhdw])$")
DURATION_UNITS = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
DEFAULT_POLL_SECONDS = 3600
DEFAULT_TIMEOUT_SECONDS = 30 * 86400
MAX_BRANCH_DEPTH = 5

ACTION_TYPES = {
    "set_field",
    "notify",
    "create_record",
    "send_email",
    "webhook",
    "update_related",
    "wait",
    "branch",
}


# ---------------------------------------------------------------------------
# Steps and program compilation
# ---------------------------------------------------------------------------


def parse_duration(value, default=None) -> int | None:
    """Parse a short duration such as ``30m``/``12h``/``3d``/``2w``."""

    if value in (None, ""):
        return default
    match = DURATION_RE.match(str(value).strip())
    if match is None:
        raise ValueError(f"Invalid duration: {value!r} (use e.g. 30m, 12h, 3d, 2w)")
    return int(match.group(1)) * DURATION_UNITS[match.group(2)]


def compile_actions(actions: list, program: list | None = None) -> list[dict]:
    """Flatten nested workflow actions into a jump-based program.

    Nested bodies are compiled straight into the shared ``program`` list, so
    every jump target is an absolute index into it.
    """

    program = [] if program is None else program
    for action in actions or []:
        if not isinstance(action, dict):
            continue

        if action.get("type") == "branch":
            branch_index = len(program)
            program.append({})
            then_start = len(program)
            compile_actions(action.get("then") or [], program)
            jump_index = None
            else_start = None
            if action.get("else"):
                jump_index = len(program)
                program.append({})
                else_start = len(program)
                compile_actions(action.get("else") or [], program)
            end = len(program)
            program[branch_index] = {
                "op": "branch",
                "condition": str(action.get("condition") or ""),
                "then": then_start,
                "else": else_start,
                "end": end,
            }
            if jump_index is not None:
                program[jump_index] = {"op": "jump", "to": end}

        elif action.get("type") == "wait":
            program.append({"op": "wait", **_compile_wait(action)})

        else:
            program.append({"op": "action", "action": action})

    return program


def _compile_wait(action: dict) -> dict:
    if action.get("duration"):
        return {"mode": "duration", "seconds": parse_duration(action["duration"], 0)}
    if action.get("until_date_field"):
        return {"mode": "until_date", "field": str(action["until_date_field"])}
    return {
        "mode": "until_condition",
        "condition": str(action.get("until_condition") or ""),
        "poll_seconds": parse_duration(action.get("poll_interval"), DEFAULT_POLL_SECONDS),
        "timeout_seconds": parse_duration(action.get("timeout"), DEFAULT_TIMEOUT_SECONDS),
    }


def _entity_type(instance) -> str:
    return (
        registry.entity_type_for_instance(instance)
        or getattr(instance, "entity_type", "")
        or ""
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_actions(actions: list, entity_type: str) -> str | None:
    """Return a message for the first invalid workflow action, or ``None``."""

    try:
        model = registry.model_for(entity_type)
        metadata_fields = set(registry.fields(entity_type))
    except (KeyError, LookupError):
        return None
    field_names = {field.name for field in model._meta.get_fields()}
    return _validate_action_list(
        actions, model, field_names, metadata_fields
    )


def _validate_action_list(
    actions, model, field_names, metadata_fields, depth=0, prefix=""
) -> str | None:
    if depth > MAX_BRANCH_DEPTH:
        return _("Actions are nested too deeply.")

    for index, action in enumerate(actions):
        label = f"{prefix}Action #{index + 1}"

        if not isinstance(action, dict) or action.get("type") not in ACTION_TYPES:
            return _("%(label)s is invalid.") % {"label": label}

        action_type = action["type"]
        problem = None

        if action_type == "set_field":
            if action.get("field") not in field_names:
                problem = _("%(label)s references an unknown field.") % {
                    "label": label
                }

        elif action_type == "webhook":
            try:
                int(action.get("webhook_id"))
            except (TypeError, ValueError):
                problem = _("%(label)s requires a numeric webhook_id.") % {
                    "label": label
                }

        elif action_type == "update_related":
            problem = _validate_update_related(action, model, label)

        elif action_type == "wait":
            problem = _validate_wait(action, metadata_fields, label)

        elif action_type == "branch":
            condition = str(action.get("condition") or "")
            if not condition.strip():
                problem = _("%(label)s requires a condition.") % {"label": label}
            else:
                try:
                    validate_expression(condition)
                except FormulaError as exc:
                    problem = _(
                        "%(label)s has an invalid condition: %(error)s"
                    ) % {"label": label, "error": exc}
            if problem is None:
                then = action.get("then")
                if not isinstance(then, list) or not then:
                    problem = _("%(label)s needs a non-empty 'then' list.") % {
                        "label": label
                    }
                else:
                    bodies = [("then", then)]
                    if action.get("else"):
                        bodies.append(("else", action["else"]))
                    for name, body in bodies:
                        if not isinstance(body, list):
                            problem = _(
                                "%(label)s: the '%(name)s' body must be a list."
                            ) % {"label": label, "name": name}
                            break
                        problem = _validate_action_list(
                            body,
                            model,
                            field_names,
                            metadata_fields,
                            depth=depth + 1,
                            prefix=f"{label} ({name}) ",
                        )
                        if problem:
                            break

        if problem:
            return problem

    return None


def _validate_update_related(action, model, label):
    relation = action.get("relation")
    related_fields = action.get("fields") or {}
    try:
        related_field = model._meta.get_field(relation)
    except Exception:  # noqa: BLE001 - unknown relation
        return _("%(label)s references an unknown relation.") % {"label": label}
    related_model = related_field.related_model
    if related_model is None:
        return _("%(label)s is not a related field.") % {"label": label}
    valid_fields = {field.name for field in related_model._meta.get_fields()}
    unknown = [name for name in related_fields if name not in valid_fields]
    if unknown:
        return _(
            "%(label)s references unknown related field(s): %(fields)s."
        ) % {"label": label, "fields": ", ".join(unknown)}
    return None


def _validate_wait(action, metadata_fields, label):
    modes = [
        key
        for key in ("duration", "until_date_field", "until_condition")
        if action.get(key)
    ]
    if len(modes) != 1:
        return _(
            "%(label)s needs exactly one of duration, until_date_field or "
            "until_condition."
        ) % {"label": label}

    mode = modes[0]
    if mode == "duration":
        try:
            parse_duration(action.get("duration"))
        except ValueError as exc:
            return _("%(label)s has an invalid duration: %(error)s") % {
                "label": label,
                "error": exc,
            }
    elif mode == "until_date_field":
        if action.get("until_date_field") not in metadata_fields:
            return _("%(label)s references an unknown date field.") % {
                "label": label
            }
    else:
        try:
            validate_expression(str(action.get("until_condition") or ""))
        except FormulaError as exc:
            return _("%(label)s has an invalid condition: %(error)s") % {
                "label": label,
                "error": exc,
            }

    for key in ("poll_interval", "timeout"):
        if action.get(key):
            try:
                parse_duration(action[key])
            except ValueError as exc:
                return _("%(label)s has an invalid %(key)s: %(error)s") % {
                    "label": label,
                    "key": key,
                    "error": exc,
                }
    return None


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


def _run_action(action: dict, instance) -> None:
    action_type = action.get("type")

    if action_type == "set_field":
        field = action["field"]
        setattr(instance, field, action.get("value"))
        instance.save(update_fields=[field])

    elif action_type == "notify":
        from omacrm.core.models import Notification
        from omacrm.core.services import notifications

        target = getattr(instance, "assigned_user", None)
        user_field = action.get("user_field")
        if user_field:
            target = getattr(instance, user_field, None)
        if target is not None:
            message = action.get("message") or f"Workflow triggered on {instance}"
            notifications.notify(
                target,
                Notification.Type.SYSTEM,
                message=str(message),
                related=instance,
            )

    elif action_type == "send_email":
        from django.conf import settings as django_settings
        from django.core.mail import send_mail
        from django.template import Context, Template
        from django.utils.html import strip_tags

        from omacrm.core.models import Note

        recipient = action.get("to") or "email_address"
        if hasattr(instance, recipient):
            recipient = getattr(instance, recipient)
        if not recipient:
            raise ValueError("No recipient email address")

        context = Context(
            {
                "record": instance,
                "object": instance,
                **{
                    field.name: getattr(instance, field.attname, "")
                    for field in instance._meta.fields
                },
            }
        )
        subject = Template(
            action.get("subject") or "Workflow notification"
        ).render(context)
        body = Template(action.get("body") or "").render(context)

        send_mail(
            subject,
            strip_tags(body),
            django_settings.DEFAULT_FROM_EMAIL,
            [recipient],
            html_message=body or None,
            fail_silently=False,
        )
        Note.objects.create(
            type=Note.Type.EMAIL,
            parent=instance,
            post=subject,
            data={"to": recipient, "workflow": True},
        )

    elif action_type == "webhook":
        from omacrm.core.models import Webhook, WebhookQueueItem
        from omacrm.core.services.webhooks import build_payload

        webhook = Webhook.objects.filter(
            pk=action.get("webhook_id"), is_active=True
        ).first()
        if webhook is None:
            raise ValueError(f"Unknown webhook: {action.get('webhook_id')}")

        event = action.get("event") or "update"
        WebhookQueueItem.objects.create(
            webhook=webhook, payload=build_payload(instance, event)
        )

    elif action_type == "update_related":
        relation = action.get("relation")
        fields = action.get("fields") or {}
        if not relation or not fields:
            raise ValueError("update_related requires relation and fields")

        manager = getattr(instance, relation, None)
        if manager is None or not hasattr(manager, "update"):
            raise ValueError(f"Unknown relation: {relation}")
        manager.update(**fields)

    elif action_type == "create_record":
        entity_type = action.get("entity_type")
        if not entity_type or not registry.has(entity_type):
            raise ValueError(f"Unknown entity type: {entity_type}")
        model = registry.model_for(entity_type)
        values = action.get("values") or {}
        record = model(**values)
        record.save()
        return record

    return None


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def _walk(program: list[dict], record, run, now=None):
    """Run a compiled program until it ends or a wait pauses it.

    Returns the datetime to resume at, or ``None`` when the program finished.
    The run's cursor is kept on the current step so a paused or failed run can
    be resumed; callers decide whether the run is persisted.
    """

    now = now or timezone.now()
    cursor = run.cursor

    while cursor < len(program):
        run.cursor = cursor

        step = program[cursor]
        op = step.get("op")

        if op == "action":
            _run_action(step.get("action") or {}, record)
            cursor += 1

        elif op == "jump":
            cursor = int(step.get("to", 0))

        elif op == "branch":
            cursor = _branch_target(step, record)

        elif op == "wait":
            if step.get("mode") == "until_condition":
                if bool(
                    evaluate(
                        str(step.get("condition") or ""), build_context(record)
                    )
                ):
                    cursor += 1
                    continue
                deadline = run.wait_deadline
                if deadline is None:
                    deadline = now + timedelta(
                        seconds=int(
                            step.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS
                        )
                    )
                    run.wait_deadline = deadline
                if now >= deadline:
                    raise RuntimeError(
                        "Wait condition timed out: %s" % step.get("condition")
                    )
                run.cursor = cursor
                return now + timedelta(
                    seconds=int(step.get("poll_seconds") or DEFAULT_POLL_SECONDS)
                )

            due = _wait_due(step, record, now)
            if due is None:
                cursor += 1
                continue
            run.cursor = cursor + 1
            return due

        else:
            cursor += 1

    return None


def _wait_due(step: dict, record, now):
    if step.get("mode") == "until_date":
        due = _as_datetime(_record_value(record, step.get("field") or ""))
        if due is None or due <= now:
            return None
        return due

    due = now + timedelta(seconds=int(step.get("seconds") or 0))
    return None if due <= now else due


def _branch_target(step: dict, record):
    matched = bool(
        evaluate(str(step.get("condition") or ""), build_context(record))
    )
    if matched:
        return int(step.get("then", 0))
    if step.get("else") is not None:
        return int(step["else"])
    return int(step.get("end", 0))


def _record_value(record, name):
    """Read a built-in or custom field value from a record."""

    entity_type = registry.entity_type_for_instance(record) or getattr(
        record, "entity_type", ""
    )
    field_def = None
    if entity_type:
        try:
            field_def = registry.field(entity_type, name)
        except Exception:  # noqa: BLE001 - metadata is best effort here
            field_def = None
    if field_def is not None and getattr(field_def, "custom", False):
        return (getattr(record, "custom_data", None) or {}).get(name)
    return getattr(record, name, None)


def _as_datetime(value):
    if isinstance(value, datetime):
        return value if timezone.is_aware(value) else timezone.make_aware(value)
    if isinstance(value, date):
        return timezone.make_aware(datetime.combine(value, time.min))
    if isinstance(value, str) and value.strip():
        from django.utils.dateparse import parse_date, parse_datetime

        parsed = parse_datetime(value.strip())
        if parsed is None:
            parsed_date = parse_date(value.strip())
            parsed = (
                datetime.combine(parsed_date, time.min) if parsed_date else None
            )
        if parsed is not None:
            return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)
    return None


def _load_record(run):
    try:
        model = registry.model_for(run.entity_type)
    except (KeyError, LookupError):
        return None
    try:
        return model.objects.filter(pk=run.record_id).first()
    except Exception:  # noqa: BLE001 - a broken lookup cancels the run
        return None


def _finish(run, status, error="", now=None):
    run.status = status
    run.last_error = error or ""
    run.execute_time = None
    run.wait_deadline = None
    run.finished_at = now or timezone.now()
    run.save(
        update_fields=[
            "status",
            "last_error",
            "cursor",
            "execute_time",
            "wait_deadline",
            "finished_at",
        ]
    )
    return run


def start_run(workflow, instance):
    """Execute a matched rule; returns a run once a wait is reached.

    The run is transient until the executed path actually pauses: rules and
    branch paths without waits leave no ``WorkflowRun`` rows behind.
    """

    from omacrm.core.models import WorkflowRun

    program = compile_actions(workflow.actions or [])
    now = timezone.now()
    run = WorkflowRun(
        workflow=workflow,
        entity_type=_entity_type(instance),
        record_id=instance.pk,
        program=program,
        status=WorkflowRun.Status.RUNNING,
    )

    token = _running.set(True)
    try:
        due = _walk(program, instance, run=run, now=now)
        if due is None:
            return None
        run.status = WorkflowRun.Status.WAITING
        run.execute_time = due
        run.save()
        return run
    except Exception:  # noqa: BLE001 - a failing rule must not break saves
        logger.exception("Workflow %s failed", workflow.pk)
        return None
    finally:
        _running.reset(token)


def advance(run, now=None):
    """Continue a run until it finishes or waits again."""

    from omacrm.core.models import WorkflowRun

    now = now or timezone.now()
    finished = {
        WorkflowRun.Status.SUCCESS,
        WorkflowRun.Status.FAILED,
        WorkflowRun.Status.CANCELLED,
    }
    if run.status in finished:
        return run

    record = _load_record(run)
    if record is None:
        return _finish(
            run,
            WorkflowRun.Status.CANCELLED,
            "The triggering record no longer exists.",
            now,
        )

    token = _running.set(True)
    try:
        run.status = WorkflowRun.Status.RUNNING
        run.execute_time = None
        due = _walk(run.program or [], record, run=run, now=now)
        if due is not None:
            run.status = WorkflowRun.Status.WAITING
            run.execute_time = due
            run.save(
                update_fields=["status", "cursor", "execute_time", "wait_deadline"]
            )
            return run
        return _finish(run, WorkflowRun.Status.SUCCESS, "", now)
    except Exception as exc:  # noqa: BLE001 - persist any step failure
        logger.exception("Workflow run %s failed", run.pk)
        return _finish(run, WorkflowRun.Status.FAILED, str(exc), now)
    finally:
        _running.reset(token)


def resume_due_runs(now=None, limit: int = 100) -> int:
    """Advance waiting runs whose resume time has passed."""

    from omacrm.core.models import WorkflowRun

    now = now or timezone.now()
    runs = list(
        WorkflowRun.objects.filter(
            status=WorkflowRun.Status.WAITING, execute_time__lte=now
        ).order_by("execute_time", "id")[:limit]
    )
    for run in runs:
        advance(run, now=now)
    return len(runs)


def run_workflows(instance, event: str) -> int:
    """Run matching workflow rules for a record event. Returns rules matched."""

    if _running.get():
        return 0

    entity_type = registry.entity_type_for_instance(instance)
    if not entity_type:
        return 0

    from omacrm.core.models import Workflow

    try:
        workflows = list(
            Workflow.objects.filter(
                entity_type=entity_type, event=event, is_active=True
            ).order_by("order", "id")
        )
    except Exception:  # noqa: BLE001 - DB may not be ready during setup
        return 0

    if not workflows:
        return 0

    token = _running.set(True)
    matched = 0
    try:
        for workflow in workflows:
            try:
                if workflow.condition:
                    if not bool(evaluate(workflow.condition, build_context(instance))):
                        continue
                matched += 1
                start_run(workflow, instance)
            except Exception:  # noqa: BLE001 - a failing rule must not break saves
                logger.exception("Workflow %s failed", workflow.pk)
    finally:
        _running.reset(token)

    return matched
