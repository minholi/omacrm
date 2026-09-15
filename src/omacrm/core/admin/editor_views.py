"""JSON endpoints backing the admin authoring editors.

The editors (``core/static/core/js/editors.js``) fetch entity metadata for
completion and post their declarations for validation. Validation delegates to
the same services that save-time ``full_clean()`` uses, so the UI cannot drift
from the server rules.
"""

import json

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from omacrm.core.metadata.registry import registry
from omacrm.core.services import dynamic_logic, formula, workflows


def _choices(field_def) -> list[dict]:
    choices = []
    for option in field_def.options or []:
        if isinstance(option, (list, tuple)) and len(option) >= 2:
            choices.append({"value": str(option[0]), "label": str(option[1])})
        else:
            choices.append({"value": str(option), "label": str(option)})
    return choices


def _formula_helpers(entity_type: str) -> list[str]:
    """Names callable in a formula script for this entity (drift-free)."""

    try:
        context = formula.build_context(registry.model_for(entity_type)())
    except Exception:  # noqa: BLE001 - completion is best effort
        return []
    return sorted(
        name
        for name, value in context.items()
        if callable(value) and not name.startswith("_")
    )


@require_GET
def editor_metadata(request, entity_type):
    if not registry.has(entity_type):
        raise Http404(f"Unknown entity type: {entity_type}")
    entity = registry.get(entity_type)

    fields = []
    for name, field_def in registry.fields(entity_type).items():
        fields.append(
            {
                "name": name,
                "label": str(field_def.display_label),
                "type": field_def.type,
                "required": bool(field_def.required),
                "readOnly": bool(field_def.read_only),
                "custom": bool(field_def.custom),
                "choices": _choices(field_def),
                "helpText": str(field_def.help_text or ""),
            }
        )

    links = []
    for name, definition in registry.link_definitions(entity_type).items():
        links.append(
            {
                "name": name,
                "label": str(definition.label),
                "multiple": bool(definition.multiple),
                "target": definition.target_entity,
                "fieldType": definition.field_type,
            }
        )

    return JsonResponse(
        {
            "entityType": entity_type,
            "label": str(entity.display_label),
            "fields": fields,
            "links": links,
            "actions": sorted(workflows.ACTION_TYPES),
            "operators": sorted(dynamic_logic.OPERATORS),
            "formulaHelpers": _formula_helpers(entity_type),
            "entityTypes": [
                {
                    "value": name,
                    "label": str(registry.get(name).display_label),
                }
                for name in registry.entity_types()
            ],
        }
    )


def _error(path: str, message) -> dict:
    return {"path": path, "message": str(message)}


def _validate_workflow_actions(entity_type: str, value) -> list[dict]:
    if not value:
        return []
    if not entity_type:
        return [_error("entity_type", "Choose an entity type first.")]
    if not registry.has(entity_type):
        return [_error("entity_type", "Unknown entity type.")]
    if not isinstance(value, list):
        return [_error("actions", "Actions must be a list.")]
    return workflows.validate_actions_detailed(value, entity_type)


def _validate_dynamic_logic(value) -> list[dict]:
    if not isinstance(value, dict):
        return [_error("condition", "Condition must be a JSON object.")]
    return [
        _error("condition", problem)
        for problem in dynamic_logic.condition_errors(value)
    ]


def _validate_formula(entity_type: str, value) -> list[dict]:
    if not entity_type or not registry.has(entity_type):
        return []
    if not isinstance(value, str):
        return [_error("script", "Script must be text.")]
    problem = formula.validate_script(value, entity_type)
    return [_error("script", problem)] if problem else []


def _validate_custom_field(entity_type: str, value) -> list[dict]:
    from omacrm.core.models import CustomField

    if not isinstance(value, dict):
        return [_error("params", "Field parameters must be a JSON object.")]
    if not entity_type or not registry.has(entity_type):
        return [_error("entity_type", "Unknown entity type.")]
    instance = CustomField(
        entity_type=entity_type,
        name=str(value.get("name") or ""),
        field_type=str(value.get("field_type") or "varchar"),
        params=value.get("params") or {},
    )
    try:
        instance.clean()
    except DjangoValidationError as exc:
        if hasattr(exc, "message_dict"):
            return [
                _error(field, "; ".join(str(item) for item in messages))
                for field, messages in exc.message_dict.items()
            ]
        return [_error("params", "; ".join(str(item) for item in exc.messages))]
    return []


def _validate_lead_capture(value) -> list[dict]:
    from django.db import models as django_models

    from omacrm.crm.models import Lead

    if not isinstance(value, list):
        return [_error("field_list", "Fields must be a list.")]
    allowed = {
        field.name
        for field in Lead._meta.get_fields()
        if isinstance(field, (django_models.TextField, django_models.CharField))
    }
    return [
        _error("field_list", f"Unknown Lead field: {name}")
        for name in value
        if name not in allowed
    ]


_VALIDATORS = {
    "workflow_actions": _validate_workflow_actions,
    "dynamic_logic": lambda entity_type, value: _validate_dynamic_logic(value),
    "formula": _validate_formula,
    "custom_field": _validate_custom_field,
    "lead_capture": lambda entity_type, value: _validate_lead_capture(value),
}


@require_POST
def editor_validate(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse(
            {"ok": False, "errors": [_error("", "Invalid JSON request.")]},
            status=400,
        )

    kind = str(payload.get("kind") or "")
    entity_type = str(payload.get("entity_type") or "")
    validator = _VALIDATORS.get(kind)
    if validator is None:
        return JsonResponse(
            {"ok": False, "errors": [_error("kind", f"Unknown editor kind: {kind}")]},
            status=400,
        )

    errors = validator(entity_type, payload.get("value"))
    return JsonResponse({"ok": not errors, "errors": errors})
