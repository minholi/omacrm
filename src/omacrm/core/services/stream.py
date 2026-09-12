from datetime import date, datetime, time
from decimal import Decimal
import re

from omacrm.core.metadata.registry import registry
from omacrm.core.services.context import get_current_user

TRACKED_EXCLUDE = {
    "id",
    "created_at",
    "modified_at",
    "created_by",
    "modified_by",
}

MENTION_RE = re.compile(r"@([A-Za-z0-9._-]+)")


def _serialize(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return str(value)


def snapshot(instance):
    """Capture the stored record state before a save (for change notes)."""

    field_map = {}
    for field in instance._meta.concrete_fields:
        if field.name in TRACKED_EXCLUDE:
            continue
        field_map[field.attname] = field.name

    state = {}
    if instance.pk and not instance._state.adding:
        row = (
            type(instance)
            ._base_manager.filter(pk=instance.pk)
            .values(*field_map.keys())
            .first()
        )
        if row is not None:
            for attname, value in row.items():
                state[field_map[attname]] = value

    if not state:
        for field in instance._meta.concrete_fields:
            if field.name in TRACKED_EXCLUDE:
                continue
            state[field.name] = getattr(instance, field.attname, None)
        if hasattr(instance, "custom_data"):
            state["custom_data"] = dict(instance.custom_data or {})

    instance._omacrm_snapshot = state


def build_changes(instance) -> dict:
    old = getattr(instance, "_omacrm_snapshot", None)
    if old is None:
        return {}

    changes = {}
    for name, old_value in old.items():
        if name == "custom_data":
            new_value = dict(getattr(instance, "custom_data", {}) or {})
        else:
            field = instance._meta.get_field(name)
            new_value = getattr(instance, field.attname, None)
        if old_value != new_value:
            changes[name] = {"was": _serialize(old_value), "became": _serialize(new_value)}
    return changes


def _emit_stream_event(instance, note) -> None:
    """Queue a real-time event for the record's assignee."""

    from omacrm.core.models import StreamEvent

    user_id = getattr(instance, "assigned_user_id", None)
    if not user_id or note.created_by_id == user_id:
        return

    entity_type = registry.entity_type_for_instance(instance)
    label = registry.get(entity_type).display_label if entity_type else "Record"
    StreamEvent.objects.create(
        user_id=user_id,
        note=note,
        message=f"{label}: {instance} — {note.get_type_display()}",
    )


def on_save(instance, created: bool = False) -> None:
    from omacrm.core.models import Note
    from omacrm.core.services import notifications

    entity_type = registry.entity_type_for_instance(instance)
    if not entity_type:
        return

    entity = registry.get(entity_type)
    if not entity.stream:
        return

    user = get_current_user()
    old = getattr(instance, "_omacrm_snapshot", None) or {}

    if created:
        note = Note.objects.create(
            type=Note.Type.CREATE,
            parent=instance,
            data={},
            created_by=user,
        )
        _emit_stream_event(instance, note)
        return

    changes = build_changes(instance)
    if changes.get("deleted", {}).get("became"):
        note = Note.objects.create(
            type=Note.Type.DELETE,
            parent=instance,
            created_by=user,
        )
        _emit_stream_event(instance, note)
        return

    if changes:
        note = Note.objects.create(
            type=Note.Type.UPDATE,
            parent=instance,
            data=changes,
            created_by=user,
        )
        _emit_stream_event(instance, note)

    if "assigned_user" in changes and instance.assigned_user_id:
        if instance.assigned_user_id != old.get("assigned_user"):
            notifications.notify_assignment(instance, actor=user)


def post_note(instance, text: str, user=None, is_internal: bool = False):
    """Create a stream post, auto-follow the author and notify users."""

    from omacrm.core.models import Note
    from omacrm.core.services import subscriptions

    note = Note.objects.create(
        type=Note.Type.POST,
        post=text,
        parent=instance,
        is_internal=is_internal,
        created_by=user or get_current_user(),
    )
    subscriptions.auto_follow_after_note(note)
    notify_mentions(note)
    notify_followers(note)
    return note


def notify_followers(note):
    """Notify the record's active followers about a stream post.

    The author is skipped so own posts stay quiet, and internal notes do not
    reach portal users.
    """

    from omacrm.core.services import notifications, subscriptions

    try:
        parent = note.parent
    except Exception:  # noqa: BLE001 - dangling generic parent
        parent = None
    if parent is None:
        return []

    followers = subscriptions.followers_of(parent)
    if note.created_by_id:
        followers = followers.exclude(pk=note.created_by_id)
    if note.is_internal:
        followers = followers.exclude(type="portal")

    label = getattr(parent, "name", None) or str(parent)
    created = []
    for user in followers:
        created.append(
            notifications.notify(
                user,
                "Stream",
                message=f"{note.created_by or 'Someone'} posted on {label}",
                related=parent,
                data={"note_id": note.pk},
            )
        )
    return created


def notify_mentions(note):
    from omacrm.core.models import User
    from omacrm.core.services import notifications

    names = set(MENTION_RE.findall(note.post or ""))
    if not names:
        return []

    created = []
    for user in User.objects.filter(user_name__in=names, is_active=True):
        if note.created_by_id == user.pk:
            continue
        created.append(
            notifications.notify(
                user,
                "Mention",
                message=f"{note.created_by or 'Someone'} mentioned you",
                related=note.parent,
                data={"note_id": note.pk},
            )
        )
    return created
