from omacrm.core.models import Notification, Preferences


def browser_popups_enabled(user) -> bool:
    """Whether browser popups are on for a user.

    The per-user preference is opt-in (``notifications_config.browser``,
    default off) and the global constance switch can still turn it off.
    """

    if user is None or not getattr(user, "pk", None):
        return False
    try:
        from constance import config

        if not getattr(config, "notification_browser_enabled", True):
            return False
    except Exception:  # noqa: BLE001 - constance may be unavailable
        pass

    preferences = Preferences.objects.filter(user=user).first()
    options = (preferences.notifications_config if preferences else {}) or {}
    return bool(options.get("browser"))


def notify(user, type: str, message: str = "", related=None, data: dict | None = None):
    if user is None:
        return None
    return Notification.objects.create(
        user=user,
        type=type,
        message=message,
        related=related,
        data=data or {},
    )


def notify_assignment(instance, actor=None):
    target = getattr(instance, "assigned_user", None)
    if target is None:
        return None
    if actor is not None and target.pk == actor.pk:
        return None
    label = getattr(instance, "name", None) or str(instance)
    return notify(
        target,
        Notification.Type.ASSIGNMENT,
        message=f"You were assigned to {label}",
        related=instance,
    )
