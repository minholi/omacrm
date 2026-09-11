"""Small, sandboxed formula interpreter.

Scripts are line based:

    field = expression        # assignment (persisted by the save)
    some_function(...)        # expression statement

Only a safe subset of Python expressions is allowed (AST whitelist). There is
no import, no attribute access on private names and only whitelisted functions
are callable.
"""

import ast
import logging
import operator
import re
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db import OperationalError, ProgrammingError
from django.utils import timezone

logger = logging.getLogger(__name__)


class FormulaError(Exception):
    pass


_ASSIGNMENT_RE = re.compile(r"^([A-Za-z_]\w*)\s*=(?!=)\s*(.+)$")
_CUSTOM_ASSIGNMENT_RE = re.compile(r"^custom(?:_data)?\.([A-Za-z_]\w*)\s*=(?!=)\s*(.+)$")

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}

_COMPARE_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
}


class SafeEvaluator(ast.NodeVisitor):
    def __init__(self, context: dict):
        self.context = context

    def visit_Expression(self, node):
        return self.visit(node.body)

    def visit_Constant(self, node):
        return node.value

    def visit_Name(self, node):
        if node.id.startswith("_") or node.id not in self.context:
            raise FormulaError(f"Unknown name: {node.id}")
        return self.context[node.id]

    def visit_BinOp(self, node):
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise FormulaError("Operator not allowed")
        return op(self.visit(node.left), self.visit(node.right))

    def visit_UnaryOp(self, node):
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            raise FormulaError("Operator not allowed")
        return op(self.visit(node.operand))

    def visit_BoolOp(self, node):
        if isinstance(node.op, ast.And):
            result = True
            for value in node.values:
                result = self.visit(value)
                if not result:
                    return result
            return result
        result = False
        for value in node.values:
            result = self.visit(value)
            if result:
                return result
        return result

    def visit_Compare(self, node):
        left = self.visit(node.left)
        for op_node, comparator in zip(node.ops, node.comparators):
            op = _COMPARE_OPS.get(type(op_node))
            if op is None:
                raise FormulaError("Comparison not allowed")
            right = self.visit(comparator)
            if not op(left, right):
                return False
            left = right
        return True

    def visit_IfExp(self, node):
        return self.visit(node.body if self.visit(node.test) else node.orelse)

    def visit_List(self, node):
        return [self.visit(element) for element in node.elts]

    def visit_Tuple(self, node):
        return tuple(self.visit(element) for element in node.elts)

    def visit_Set(self, node):
        return {self.visit(element) for element in node.elts}

    def visit_Dict(self, node):
        return {
            self.visit(key): self.visit(value)
            for key, value in zip(node.keys, node.values)
        }

    def visit_Subscript(self, node):
        return self.visit(node.value)[self.visit(node.slice)]

    def visit_Index(self, node):
        return self.visit(node.value)

    def visit_Attribute(self, node):
        if node.attr.startswith("_"):
            raise FormulaError("Private attributes are not allowed")
        value = self.visit(node.value)
        if isinstance(value, dict):
            return value.get(node.attr)
        return getattr(value, node.attr)

    def visit_Call(self, node):
        if not isinstance(node.func, ast.Name):
            raise FormulaError("Only direct function calls are allowed")
        func = self.context.get(node.func.id)
        if func is None or not callable(func):
            raise FormulaError(f"Function not allowed: {node.func.id}")
        args = [self.visit(arg) for arg in node.args]
        kwargs = {kw.arg: self.visit(kw.value) for kw in node.keywords}
        return func(*args, **kwargs)

    def generic_visit(self, node):
        raise FormulaError(f"Unsupported expression: {type(node).__name__}")


def build_context(instance, user=None) -> dict:
    def notify(message):
        from omacrm.core.models import Notification
        from omacrm.core.services import notifications

        target = getattr(instance, "assigned_user", None)
        if target is not None:
            notifications.notify(
                target,
                Notification.Type.SYSTEM,
                message=str(message),
                related=instance,
            )
        return True

    def set_value(field, value):
        setattr(instance, field, value)
        return value

    def get_value(field, default=None):
        return getattr(instance, field, default)

    def update(field, value):
        """Persist a single field without re-triggering hooks (after save)."""
        type(instance).objects.filter(pk=instance.pk).update(**{field: value})
        setattr(instance, field, value)
        return value

    def log(message):
        logger.info("Formula: %s", message)
        return True

    context = {
        "record": instance,
        "instance": instance,
        "user": user,
        "now": timezone.now,
        "today": timezone.localdate,
        "days": lambda value: timedelta(days=value),
        "hours": lambda value: timedelta(hours=value),
        "notify": notify,
        "set": set_value,
        "get": get_value,
        "update": update,
        "log": log,
        "Decimal": Decimal,
        "date": date,
        "datetime": datetime,
        "len": len,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "round": round,
        "abs": abs,
        "min": min,
        "max": max,
        "sum": sum,
    }

    # Expose record fields as bare names so conditions like
    # ``status == 'Completed'`` work naturally.
    for field in instance._meta.concrete_fields:
        context.setdefault(field.name, getattr(instance, field.name, None))

    return context


def evaluate(source: str, context: dict):
    try:
        tree = ast.parse(source.strip(), mode="eval")
    except SyntaxError as exc:
        raise FormulaError(f"Syntax error: {exc.msg}") from exc
    try:
        return SafeEvaluator(context).visit(tree)
    except FormulaError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface as a formula error
        raise FormulaError(str(exc)) from exc


def interpret(script: str, instance, user=None, dry_run: bool = False):
    """Execute a multiline formula script against a record instance."""

    context = build_context(instance, user=user)
    for line_number, raw_line in enumerate((script or "").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        custom_match = _CUSTOM_ASSIGNMENT_RE.match(line)
        if custom_match:
            if not hasattr(instance, "custom_data"):
                raise FormulaError(
                    f"Line {line_number}: record has no custom fields"
                )
            key = custom_match.group(1)
            value = evaluate(custom_match.group(2), context)
            if not dry_run:
                data = dict(instance.custom_data or {})
                data[key] = value
                instance.custom_data = data
            continue

        match = _ASSIGNMENT_RE.match(line)
        if match:
            field = match.group(1)
            expression = match.group(2)
            if not hasattr(instance, field):
                raise FormulaError(
                    f"Line {line_number}: unknown field '{field}'"
                )
            value = evaluate(expression, context)
            if not dry_run:
                setattr(instance, field, value)
            continue

        evaluate(line, context)

    return instance


_formula_cache: dict[tuple[str, str], list] = {}


def invalidate_formula_cache():
    _formula_cache.clear()


def active_formulas(entity_type: str, event: str):
    key = (entity_type, event)
    if key not in _formula_cache:
        from omacrm.core.models import Formula

        try:
            _formula_cache[key] = list(
                Formula.objects.filter(
                    entity_type=entity_type, event=event, is_active=True
                ).order_by("order", "id")
            )
        except (OperationalError, ProgrammingError):
            _formula_cache[key] = []
    return _formula_cache[key]


def run_formulas(instance, event: str) -> None:
    from omacrm.core.metadata.registry import registry
    from omacrm.core.services.context import get_current_user

    entity_type = registry.entity_type_for_instance(instance)
    if not entity_type:
        return

    formulas = active_formulas(entity_type, event)
    if not formulas:
        return

    user = get_current_user()
    for formula in formulas:
        try:
            interpret(formula.script, instance, user=user)
        except FormulaError:
            if event == "before_save":
                raise
            logger.exception("After-save formula %s failed", formula.pk)
