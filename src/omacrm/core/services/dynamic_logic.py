"""Dynamic logic: field state driven by the values of other fields.

Rules are :class:`~omacrm.core.models.DynamicLogic` rows: an entity, a field,
an action (``visible`` / ``required`` / ``readonly``) and a condition tree
mirroring EspoCRM's condition vocabulary.  The evaluator is pure (no database
access) and never raises: a malformed condition simply does not match, so a
bad rule can never break a form.
"""

import logging
import re
from datetime import date, datetime, time as dt_time
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import OperationalError, ProgrammingError
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

logger = logging.getLogger(__name__)

GROUP_OPERATORS = {"and", "or", "not"}
LEAF_OPERATORS = {
    "equals",
    "notEquals",
    "isTrue",
    "isFalse",
    "isEmpty",
    "isNotEmpty",
    "contains",
    "notContains",
    "startsWith",
    "endsWith",
    "matches",
    "has",
    "notHas",
    "in",
    "notIn",
    "greaterThan",
    "lessThan",
    "greaterThanOrEquals",
    "lessThanOrEquals",
    "isToday",
    "inFuture",
    "inPast",
}
UNARY_OPERATORS = {
    "isTrue",
    "isFalse",
    "isEmpty",
    "isNotEmpty",
    "isToday",
    "inFuture",
    "inPast",
}
OPERATORS = GROUP_OPERATORS | LEAF_OPERATORS


# -- value coercion ---------------------------------------------------------


def _is_empty(value) -> bool:
    if value is None or value == "":
        return True
    return isinstance(value, (list, tuple, set, dict)) and not value


def _to_bool(value):
    """Best-effort boolean coercion; ``None`` when the value is ambiguous."""

    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "on"}:
            return True
        if text in {"false", "0", "no", "off"}:
            return False
    return None


def _to_number(value):
    """Best-effort numeric coercion (numbers and numeric strings)."""

    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return Decimal(text)
        except (InvalidOperation, ValueError):
            return None
    return None


def _to_datetime(value):
    """Coerce dates/datetimes/strings to an aware local datetime."""

    if isinstance(value, datetime):
        result = value
    elif isinstance(value, date):
        result = datetime.combine(value, dt_time.min)
    elif isinstance(value, str):
        result = parse_datetime(value)
        if result is None:
            parsed = parse_date(value)
            if parsed is None:
                return None
            result = datetime.combine(parsed, dt_time.min)
    else:
        return None

    if timezone.is_aware(result):
        if settings.USE_TZ:
            return timezone.localtime(result)
        return result.replace(tzinfo=None)
    if settings.USE_TZ:
        return timezone.make_aware(result)
    return result


def _text(value) -> str:
    return value if isinstance(value, str) else str(value)


def _any_equal(collection, expected) -> bool:
    return any(_equal(item, expected) for item in collection)


def _equal(actual, expected) -> bool:
    if isinstance(actual, bool) or isinstance(expected, bool):
        actual_bool = _to_bool(actual)
        expected_bool = _to_bool(expected)
        if actual_bool is None or expected_bool is None:
            return actual == expected
        return actual_bool == expected_bool

    if isinstance(actual, (date, datetime)) or isinstance(expected, (date, datetime)):
        actual_dt = _to_datetime(actual)
        expected_dt = _to_datetime(expected)
        if actual_dt is not None and expected_dt is not None:
            return actual_dt == expected_dt

    actual_number = _to_number(actual)
    expected_number = _to_number(expected)
    if actual_number is not None and expected_number is not None:
        return actual_number == expected_number

    return actual == expected


def _contains(actual, expected) -> bool:
    if actual is None:
        return False
    return _text(expected) in _text(actual)


def _matches(actual, expected) -> bool:
    if actual is None:
        return False
    try:
        return re.search(_text(expected), _text(actual)) is not None
    except re.error:
        return False


def _has(actual, expected) -> bool:
    if isinstance(actual, dict):
        collection = list(actual.keys())
    elif isinstance(actual, (list, tuple, set)):
        collection = list(actual)
    elif isinstance(actual, str):
        return _contains(actual, expected)
    else:
        return False
    return _any_equal(collection, expected)


def _in(actual, expected) -> bool:
    if isinstance(expected, str):
        return actual is not None and _text(actual) in expected
    if isinstance(expected, dict):
        collection = list(expected.keys())
    elif isinstance(expected, (list, tuple, set)):
        collection = list(expected)
    else:
        return False
    return _any_equal(collection, actual)


def _greater_than(actual, expected) -> bool:
    actual_number = _to_number(actual)
    expected_number = _to_number(expected)
    if actual_number is None or expected_number is None:
        return False
    return actual_number > expected_number


def _less_than(actual, expected) -> bool:
    actual_number = _to_number(actual)
    expected_number = _to_number(expected)
    if actual_number is None or expected_number is None:
        return False
    return actual_number < expected_number


def _greater_than_or_equals(actual, expected) -> bool:
    return _greater_than(actual, expected) or _equal(actual, expected)


def _less_than_or_equals(actual, expected) -> bool:
    return _less_than(actual, expected) or _equal(actual, expected)


def _is_today(actual, _expected) -> bool:
    value = _to_datetime(actual)
    return value is not None and value.date() == timezone.localdate()


def _in_future(actual, _expected) -> bool:
    value = _to_datetime(actual)
    return value is not None and value > timezone.now()


def _in_past(actual, _expected) -> bool:
    value = _to_datetime(actual)
    return value is not None and value < timezone.now()


_OPERATOR_HANDLERS = {
    "equals": _equal,
    "notEquals": lambda actual, expected: not _equal(actual, expected),
    "isTrue": lambda actual, _expected: _to_bool(actual) is True,
    "isFalse": lambda actual, _expected: _to_bool(actual) is False,
    "isEmpty": lambda actual, _expected: _is_empty(actual),
    "isNotEmpty": lambda actual, _expected: not _is_empty(actual),
    "contains": _contains,
    "notContains": lambda actual, expected: not _contains(actual, expected),
    "startsWith": lambda actual, expected: actual is not None
    and _text(actual).startswith(_text(expected)),
    "endsWith": lambda actual, expected: actual is not None
    and _text(actual).endswith(_text(expected)),
    "matches": _matches,
    "has": _has,
    "notHas": lambda actual, expected: not _has(actual, expected),
    "in": _in,
    "notIn": lambda actual, expected: not _in(actual, expected),
    "greaterThan": _greater_than,
    "lessThan": _less_than,
    "greaterThanOrEquals": _greater_than_or_equals,
    "lessThanOrEquals": _less_than_or_equals,
    "isToday": _is_today,
    "inFuture": _in_future,
    "inPast": _in_past,
}


def _evaluate_node(node, values) -> bool:
    if not isinstance(node, dict):
        return False

    node_type = node.get("type")
    if node_type in {"and", "or"}:
        children = node.get("value")
        if not isinstance(children, list):
            return False
        if node_type == "and":
            return all(_evaluate_node(child, values) for child in children)
        return any(_evaluate_node(child, values) for child in children)

    if node_type == "not":
        child = node.get("value")
        if not isinstance(child, dict):
            return False
        return not _evaluate_node(child, values)

    attribute = node.get("attribute")
    if not isinstance(attribute, str) or not attribute:
        return False
    handler = _OPERATOR_HANDLERS.get(node_type)
    if handler is None:
        return False
    return bool(handler(values.get(attribute), node.get("value")))


def evaluate(condition, values) -> bool:
    """Evaluate a condition tree against a mapping of field values.

    Pure and defensive: any malformed node (or any unexpected error) makes the
    condition not match instead of raising.
    """

    try:
        if not isinstance(values, dict):
            values = {}
        return bool(_evaluate_node(condition, values))
    except Exception:  # noqa: BLE001 - a bad rule must never break a form
        logger.exception("Dynamic logic condition failed to evaluate")
        return False


def condition_errors(condition, path: str = "condition") -> list[str]:
    """Human-readable structural problems of a condition tree (admin help)."""

    if not isinstance(condition, dict):
        return [f"{path} must be a JSON object."]
    if not condition:
        return [f"{path} must contain at least one condition."]

    node_type = condition.get("type")
    if node_type not in OPERATORS:
        return [f"{path}: unknown operator '{node_type}'."]

    problems: list[str] = []
    if node_type in {"and", "or"}:
        children = condition.get("value")
        if not isinstance(children, list) or not children:
            problems.append(
                f"{path}: '{node_type}' needs a non-empty list of child conditions."
            )
        else:
            for index, child in enumerate(children):
                problems.extend(
                    condition_errors(child, f"{path}.value[{index}]")
                )
    elif node_type == "not":
        child = condition.get("value")
        if not isinstance(child, dict):
            problems.append(f"{path}: 'not' needs a child condition.")
        else:
            problems.extend(condition_errors(child, f"{path}.value"))
    else:
        if not condition.get("attribute"):
            problems.append(f"{path}: '{node_type}' needs an attribute.")
        if node_type not in UNARY_OPERATORS and "value" not in condition:
            problems.append(f"{path}: '{node_type}' needs a value.")
    return problems


# -- rule lookup and field states -------------------------------------------


_rules_cache: dict[str, list] = {}


def invalidate_dynamic_logic_cache() -> None:
    """Drop the in-process rule cache.

    Wired to the ``post_save``/``post_delete`` signals in ``core.apps``, so the
    cache is only cleared in the process that performed the write. Rules changed
    from a shell/console, or by another worker, therefore stay stale in the
    serving process until it restarts — which is the case this cache trades for
    one query per form render.
    """

    _rules_cache.clear()


def active_rules(entity_type: str) -> list:
    """Active ``DynamicLogic`` rows for an entity, cached in memory."""

    if entity_type not in _rules_cache:
        from omacrm.core.models import DynamicLogic

        try:
            _rules_cache[entity_type] = list(
                DynamicLogic.objects.filter(
                    entity_type=entity_type, is_active=True
                ).order_by("field_name", "action", "id")
            )
        except (OperationalError, ProgrammingError):
            _rules_cache[entity_type] = []
    return _rules_cache[entity_type]


def metadata_fields(entity_type: str) -> dict:
    """Metadata fields plus custom links for an entity."""

    from omacrm.core.metadata.registry import registry

    fields = dict(registry.fields(entity_type))
    fields.update(registry.link_fields(entity_type))
    return fields


def metadata_defaults(entity_type: str) -> dict[str, dict[str, bool]]:
    """State of every field before any rule is applied."""

    return {
        name: {
            "visible": True,
            "required": bool(field_def.required),
            "readonly": False,
        }
        for name, field_def in metadata_fields(entity_type).items()
    }


def field_states(entity_type: str, values) -> dict[str, dict[str, bool]]:
    """Per-field ``{"visible", "required", "readonly"}`` for submitted values.

    Starts from the metadata defaults and applies the entity's active rules.
    Rules for one action are OR-ed: a field is visible/required/read-only when
    at least one of its rules for that action matches.  A rule whose condition
    does not match clears the corresponding default (so a field made
    conditionally required is not required while the condition is false).
    """

    states = metadata_defaults(entity_type)
    rules = active_rules(entity_type)
    if not rules:
        return states

    values = values if isinstance(values, dict) else {}
    by_field: dict[str, list] = {}
    for rule in rules:
        by_field.setdefault(rule.field_name, []).append(rule)

    for name, field_rules in by_field.items():
        state = states.get(name)
        if state is None:
            continue
        for action in ("visible", "required", "readonly"):
            action_rules = [rule for rule in field_rules if rule.action == action]
            if action_rules:
                state[action] = any(
                    evaluate(rule.condition, values) for rule in action_rules
                )
    return states


def frontend_config(entity_type: str) -> dict:
    """JSON payload for the follow-up client-side dynamic logic."""

    return {
        "entityType": entity_type,
        "fields": metadata_defaults(entity_type),
        "rules": [
            {
                "id": rule.pk,
                "field": rule.field_name,
                "action": rule.action,
                "condition": rule.condition,
            }
            for rule in active_rules(entity_type)
        ],
    }
