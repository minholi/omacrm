"""Espo-style ``where`` query parameter translated to Django ``Q`` objects.

Accepted shapes::

    [{"type": "equals", "attribute": "stage", "value": "Proposal"}]
    {"type": "and", "value": [
        {"type": "contains", "attribute": "name", "value": "acme"},
        {"type": "not", "value": [
            {"type": "equals", "attribute": "type", "value": "Reseller"}
        ]},
    ]}
"""

import json

from django.db.models import Q
from rest_framework.exceptions import ValidationError

from omacrm.core.metadata.registry import registry

_COMPARISONS = {
    "equals": "",
    "notEquals": "",
    "contains": "__icontains",
    "notContains": "__icontains",
    "startsWith": "__istartswith",
    "endsWith": "__iendswith",
    "greaterThan": "__gt",
    "greaterThanOrEquals": "__gte",
    "lessThan": "__lt",
    "lessThanOrEquals": "__lte",
    "in": "__in",
    "notIn": "__in",
}

_NEGATED = {"notEquals", "notContains", "notIn"}


def _field_defs(entity_type: str) -> dict:
    try:
        return registry.fields(entity_type)
    except KeyError as exc:
        raise ValidationError({"where": str(exc)}) from exc


def _base_path(field_def) -> str:
    return f"custom_data__{field_def.name}" if field_def.custom else field_def.name


def _leaf(entity_type: str, node: dict, field_defs: dict) -> Q:
    node_type = node.get("type")
    attribute = node.get("attribute")
    value = node.get("value")

    field_def = field_defs.get(attribute)
    if field_def is None:
        raise ValidationError({"where": f"Unknown attribute: {attribute}"})

    base = _base_path(field_def)

    if node_type in {"isNull", "isNotNull"}:
        is_null = bool(value) if node_type == "isNull" else not value
        return Q(**{f"{base}__isnull": is_null})

    if node_type == "between":
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise ValidationError(
                {"where": "between expects a two-item value list"}
            )
        return Q(**{f"{base}__gte": value[0]}) & Q(**{f"{base}__lte": value[1]})

    lookup = _COMPARISONS.get(node_type)
    if lookup is None:
        raise ValidationError({"where": f"Unknown condition: {node_type}"})

    if node_type in {"in", "notIn"} and not isinstance(value, (list, tuple)):
        raise ValidationError({"where": f"{node_type} expects a list value"})

    condition = Q(**{f"{base}{lookup}": value})
    return ~condition if node_type in _NEGATED else condition


def build_q(entity_type: str, where) -> Q:
    field_defs = _field_defs(entity_type)

    if isinstance(where, list):
        condition = Q()
        for node in where:
            condition &= build_q(entity_type, node)
        return condition

    if not isinstance(where, dict):
        raise ValidationError({"where": "Expected an object or a list of objects"})

    node_type = where.get("type")

    if node_type in {"and", "or", "not"}:
        items = where.get("value")
        if not isinstance(items, (list, tuple)):
            raise ValidationError({"where": f"{node_type} expects a list value"})

        if node_type == "or":
            if not items:
                return Q()
            condition = build_q(entity_type, items[0])
            for node in items[1:]:
                condition |= build_q(entity_type, node)
            return condition

        condition = Q()
        for node in items:
            condition &= build_q(entity_type, node)
        return ~condition if node_type == "not" else condition

    return _leaf(entity_type, where, field_defs)


def parse_where(entity_type: str, raw) -> Q:
    if isinstance(raw, (list, dict)):
        return build_q(entity_type, raw)

    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError({"where": "Invalid JSON"}) from exc
    return build_q(entity_type, data)
