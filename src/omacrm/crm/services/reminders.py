from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from omacrm.core.services.jobs import jobs
from omacrm.crm.models import Reminder, ReminderType


def sync_reminders(instance):
    """Rebuild pending reminders for a Task/Call/Meeting from its JSON list."""

    content_type = ContentType.objects.get_for_model(type(instance))
    Reminder.objects.filter(
        entity_type=content_type, entity_id=instance.pk, is_submitted=False
    ).delete()

    reminder_items = instance.reminders or []
    base = instance.date_end or instance.date_start
    if base is None or not reminder_items:
        return []

    created = []
    for item in reminder_items:
        if not isinstance(item, dict):
            continue
        seconds = int(item.get("seconds", 0) or 0)
        reminder_type = item.get("type") or ReminderType.POPUP
        if reminder_type not in ReminderType.values:
            reminder_type = ReminderType.POPUP
        created.append(
            Reminder.objects.create(
                remind_at=base - timedelta(seconds=seconds),
                start_at=base,
                type=reminder_type,
                seconds=seconds,
                user=instance.assigned_user,
                entity=instance,
            )
        )
    return created


@jobs.register("crm.send_reminders", name="Send due reminders")
def send_due_reminders(job):
    from omacrm.core.models import Notification
    from omacrm.core.services import notifications

    now = timezone.now()
    due = Reminder.objects.filter(
        is_submitted=False, remind_at__lte=now
    ).select_related("user", "entity_type")

    sent = 0
    for reminder in due:
        if reminder.user_id:
            label = str(reminder.entity) if reminder.entity else "an item"
            notifications.notify(
                reminder.user,
                Notification.Type.SYSTEM,
                message=f"Reminder: {label}",
                related=reminder.entity,
                data={"reminder_id": reminder.pk},
            )
            sent += 1
        reminder.is_submitted = True
        reminder.save(update_fields=["is_submitted"])
    return sent
