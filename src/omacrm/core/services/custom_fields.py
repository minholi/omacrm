"""Helpers for advanced custom-field types (phone, number, files, foreign)."""

from datetime import date, datetime, time as dt_time
from decimal import Decimal

FILE_TYPES = {"file", "image", "attachmentMultiple"}
HIDDEN_TYPES = {"foreign"} | FILE_TYPES

ADDRESS_KEYS = ("street", "city", "state", "postal_code", "country")


def json_safe(value):
    """Convert Decimal/datetime (and nested structures) to JSON values."""

    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dt_time):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def next_number(entity_type: str, field_name: str, params: dict | None = None):
    """Advance the per-entity sequence and format the value."""

    from django.db import transaction

    from omacrm.core.models import NextNumber

    with transaction.atomic():
        row, _created = (
            NextNumber.objects.select_for_update().get_or_create(
                entity_type=entity_type, field_name=field_name
            )
        )
        row.value += 1
        row.save(update_fields=["value"])

    params = params or {}
    prefix = params.get("prefix") or ""
    padding = int(params.get("padding") or 0)
    if prefix or padding:
        return f"{prefix}{row.value:0{padding}d}"
    return row.value


def normalize_custom_data(instance, field_defs, data, *, create: bool) -> dict:
    """Apply phone/number/decimal transformations before saving."""

    from omacrm.core.metadata.registry import registry

    result = dict(data or {})
    entity_type = (
        getattr(instance, "entity_type", "")
        or registry.entity_type_for_instance(instance)
        or ""
    )

    for field_def in field_defs:
        if field_def.type == "foreign":
            result.pop(field_def.name, None)
            continue
        if field_def.type in FILE_TYPES:
            continue
        value = result.get(field_def.name)

        if field_def.type == "number":
            if not create:
                result[field_def.name] = (instance.custom_data or {}).get(
                    field_def.name
                )
            elif value in (None, ""):
                result[field_def.name] = next_number(
                    entity_type, field_def.name, field_def.params
                )
            continue

        if value in (None, ""):
            result.pop(field_def.name, None)
            continue

        if field_def.type == "phone":
            from omacrm.core.services.phone import normalize_phone

            normalized = normalize_phone(str(value))
            if normalized:
                value = normalized
        if field_def.type in {"float", "decimal", "currency"}:
            value = json_safe(value)
        result[field_def.name] = json_safe(value)

    return result


def foreign_value(record, field_def) -> str:
    """Read-only value of a field through a custom link."""

    from omacrm.core.services import relations

    params = field_def.params or {}
    link = params.get("link")
    target_field = params.get("field")
    if not link or not target_field:
        return "-"

    related = relations.get_related(record, link)
    if not related:
        return "-"
    target = related[0]
    model_field_names = {field.name for field in target._meta.concrete_fields}
    if target_field in model_field_names:
        value = getattr(target, target_field)
    else:
        value = (getattr(target, "custom_data", {}) or {}).get(target_field)
    if value in (None, ""):
        return "-"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _attachment_ids(value) -> list[int]:
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple)):
        return [int(item) for item in value]
    return [int(value)]


def attachments_for(value) -> list:
    from omacrm.core.models import Attachment

    ids = _attachment_ids(value)
    if not ids:
        return []
    attachments = {row.pk: row for row in Attachment.objects.filter(pk__in=ids)}
    return [attachments[pk] for pk in ids if pk in attachments]


def display_value(record, field_def) -> str:
    """Human-readable representation used by changelist columns."""

    from omacrm.core.metadata.fields import display_custom_value

    if field_def.type == "foreign":
        return foreign_value(record, field_def)
    value = (getattr(record, "custom_data", {}) or {}).get(field_def.name)
    if field_def.type == "address":
        if not isinstance(value, dict):
            return "-"
        parts = [value.get(key) for key in ADDRESS_KEYS]
        text = ", ".join(str(part) for part in parts if part)
        return text or "-"
    if field_def.type in FILE_TYPES:
        attachments = attachments_for(value)
        if not attachments:
            return "-"
        return ", ".join(row.name for row in attachments[:3]) + (
            f" +{len(attachments) - 3}" if len(attachments) > 3 else ""
        )
    if field_def.type == "number" and value in (None, ""):
        return "-"
    return display_custom_value(field_def, value)


def _delete_attachments(value) -> None:
    for attachment in attachments_for(value):
        if attachment.file:
            attachment.file.delete(save=False)
        attachment.delete()


def apply_attachment_fields(instance, field_defs, cleaned_data, request, data) -> dict:
    """Persist uploaded files for file/image/attachmentMultiple fields."""

    from omacrm.core.models import Attachment

    updated = dict(data or {})
    for field_def in field_defs:
        if field_def.type not in FILE_TYPES:
            continue
        field_name = f"custom__{field_def.name}"
        uploaded = cleaned_data.get(field_name)
        cleared = bool(request and f"{field_name}-clear" in request.POST)
        existing = updated.get(field_def.name)

        if field_def.type == "attachmentMultiple":
            if not uploaded:
                continue
            created = []
            for upload in uploaded:
                attachment = Attachment(
                    related=instance, name=upload.name, file=upload
                )
                attachment.save()
                created.append(attachment.pk)
            updated[field_def.name] = _attachment_ids(existing) + created
            continue

        if cleared:
            _delete_attachments(existing)
            updated.pop(field_def.name, None)
            existing = None
        if uploaded:
            _delete_attachments(existing)
            attachment = Attachment(related=instance, name=uploaded.name, file=uploaded)
            attachment.save()
            updated[field_def.name] = attachment.pk

    return updated
