from omacrm.core.models import Notification


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
