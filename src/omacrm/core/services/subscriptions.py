"""Stars (favourites) and record following (stream subscriptions).

Records are identified by their metadata entity type (``"Account"``,
``"Project"``, ...) plus their primary key — the same generic convention the
stream uses — so runtime custom entities work exactly like built-in ones.
List views annotate the current user's states with ``Exists`` subqueries so a
whole page is one query instead of one query per row.
"""

from django.db import models

from omacrm.core.metadata.registry import registry


def _identity(entity):
    """Return ``(entity_type, pk)`` for a record, or ``("", None)``."""

    if entity is None or getattr(entity, "pk", None) is None:
        return "", None
    entity_type = registry.entity_type_for_instance(entity)
    if not entity_type:
        entity_type = getattr(entity, "entity_type", "") or ""
    return entity_type, entity.pk


def _stream_enabled(entity_type: str) -> bool:
    if not entity_type:
        return False
    try:
        return bool(registry.get(entity_type).stream)
    except KeyError:
        return False


def stream_entity_choices() -> list[tuple[str, str]]:
    """``(value, label)`` pairs of stream-enabled entity types."""

    entities = [item for item in registry.entities().values() if item.stream]
    return sorted(
        ((item.entity_type, item.display_label) for item in entities),
        key=lambda pair: str(pair[1]).lower(),
    )


# -- stars ------------------------------------------------------------------


def is_starred(user, entity) -> bool:
    from omacrm.core.models import StarSubscription

    if user is None or not getattr(user, "is_authenticated", False):
        return False
    entity_type, entity_id = _identity(entity)
    if not entity_type or entity_id is None:
        return False
    return StarSubscription.objects.filter(
        user=user, entity_type=entity_type, entity_id=entity_id
    ).exists()


def set_starred(user, entity, value: bool) -> bool:
    """Idempotently star or unstar a record; returns the resulting state."""

    from omacrm.core.models import StarSubscription

    if user is None or not getattr(user, "is_authenticated", False):
        return False
    entity_type, entity_id = _identity(entity)
    if not entity_type or entity_id is None:
        return False
    if value:
        StarSubscription.objects.get_or_create(
            user=user, entity_type=entity_type, entity_id=entity_id
        )
        return True
    StarSubscription.objects.filter(
        user=user, entity_type=entity_type, entity_id=entity_id
    ).delete()
    return False


# -- following ---------------------------------------------------------------


def is_following(user, entity) -> bool:
    from omacrm.core.models import StreamSubscription

    if user is None or not getattr(user, "is_authenticated", False):
        return False
    entity_type, entity_id = _identity(entity)
    if not entity_type or entity_id is None:
        return False
    return StreamSubscription.objects.filter(
        user=user, entity_type=entity_type, entity_id=entity_id
    ).exists()


def set_following(user, entity, value: bool) -> bool:
    """Idempotently follow or unfollow a record; returns the resulting state.

    Following is only meaningful for stream-enabled entity types.
    """

    from omacrm.core.models import StreamSubscription

    if user is None or not getattr(user, "is_authenticated", False):
        return False
    entity_type, entity_id = _identity(entity)
    if not entity_type or entity_id is None:
        return False
    if value:
        if not _stream_enabled(entity_type):
            return False
        StreamSubscription.objects.get_or_create(
            user=user, entity_type=entity_type, entity_id=entity_id
        )
        return True
    StreamSubscription.objects.filter(
        user=user, entity_type=entity_type, entity_id=entity_id
    ).delete()
    return False


def followers_of(entity):
    """Active users following a record."""

    from omacrm.core.models import User

    entity_type, entity_id = _identity(entity)
    if not entity_type or entity_id is None:
        return User.objects.none()
    return User.objects.filter(
        is_active=True,
        stream_subscriptions__entity_type=entity_type,
        stream_subscriptions__entity_id=entity_id,
    ).distinct()


# -- list annotations / filters ---------------------------------------------


def _flag_annotation(queryset, user, entity_type: str, model, name: str):
    if (
        not entity_type
        or user is None
        or not getattr(user, "is_authenticated", False)
    ):
        return queryset.annotate(
            **{name: models.Value(False, output_field=models.BooleanField())}
        )
    flag = model.objects.filter(
        user=user,
        entity_type=entity_type,
        entity_id=models.OuterRef("pk"),
    )
    return queryset.annotate(**{name: models.Exists(flag)})


def annotate_starred(queryset, user, entity_type: str):
    """Annotate ``starred`` for the current user in a single query."""

    from omacrm.core.models import StarSubscription

    return _flag_annotation(
        queryset, user, entity_type, StarSubscription, "starred"
    )


def annotate_followed(queryset, user, entity_type: str):
    """Annotate ``followed`` for the current user in a single query."""

    from omacrm.core.models import StreamSubscription

    return _flag_annotation(
        queryset, user, entity_type, StreamSubscription, "followed"
    )


def filter_starred(queryset, user, entity_type: str, value: bool = True):
    return annotate_starred(queryset, user, entity_type).filter(starred=value)


def filter_followed(queryset, user, entity_type: str, value: bool = True):
    return annotate_followed(queryset, user, entity_type).filter(followed=value)


# -- auto-follow -------------------------------------------------------------


def auto_follow_entity_types(user) -> set[str]:
    """Entity types the user follows automatically, from their preferences."""

    if user is None or not getattr(user, "is_authenticated", False):
        return set()
    from omacrm.core.models import Preferences

    stored = (
        Preferences.objects.filter(user=user)
        .values_list("auto_follow_entity_types", flat=True)
        .first()
        or []
    )
    return {item for item in stored if _stream_enabled(item)}


def maybe_auto_follow(user, entity) -> bool:
    """Follow a record for the user when its type is in their preferences."""

    entity_type, _entity_id = _identity(entity)
    if not entity_type or entity_type not in auto_follow_entity_types(user):
        return False
    return set_following(user, entity, True)


def auto_follow_created(instance) -> int:
    """Follow a freshly created record for every user asking for its type."""

    from omacrm.core.models import Preferences, StreamSubscription, User

    entity_type, entity_id = _identity(instance)
    if not entity_type or entity_id is None or not _stream_enabled(entity_type):
        return 0

    user_ids = [
        pref.user_id
        for pref in Preferences.objects.filter(
            user__is_active=True,
            user__type__in=(User.Type.REGULAR, User.Type.ADMIN),
        ).only("user_id", "auto_follow_entity_types")
        if entity_type in (pref.auto_follow_entity_types or [])
    ]
    if not user_ids:
        return 0

    existing = set(
        StreamSubscription.objects.filter(
            entity_type=entity_type, entity_id=entity_id, user_id__in=user_ids
        ).values_list("user_id", flat=True)
    )
    new_ids = [user_id for user_id in user_ids if user_id not in existing]
    if not new_ids:
        return 0

    StreamSubscription.objects.bulk_create(
        [
            StreamSubscription(
                user_id=user_id, entity_type=entity_type, entity_id=entity_id
            )
            for user_id in new_ids
        ]
    )
    return len(new_ids)


def auto_follow_after_note(note) -> bool:
    """Auto-follow the parent record for the note's author."""

    author = getattr(note, "created_by", None)
    try:
        parent = note.parent
    except Exception:  # noqa: BLE001 - dangling generic relation
        parent = None
    if author is None or parent is None:
        return False
    return maybe_auto_follow(author, parent)
