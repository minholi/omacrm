from omacrm.core.models import Job
from omacrm.core.services.jobs import jobs


@jobs.register("system.noop", name="No-op / connectivity check")
def noop(job: Job) -> None:
    """Does nothing; useful for testing the job runner."""


@jobs.register("system.cleanup_jobs", name="Cleanup old job records")
def cleanup_jobs(job: Job) -> None:
    from datetime import timedelta

    from django.utils import timezone

    cutoff = timezone.now() - timedelta(days=30)
    Job.objects.filter(status=Job.Status.SUCCESS, finished_at__lt=cutoff).delete()


@jobs.register("core.cleanup_stream_events", name="Cleanup old stream events")
def cleanup_stream_events(job: Job) -> None:
    from datetime import timedelta

    from django.utils import timezone

    from omacrm.core.models import StreamEvent

    cutoff = timezone.now() - timedelta(days=7)
    StreamEvent.objects.filter(created_at__lt=cutoff).delete()


@jobs.register("core.send_notification_emails", name="Email unread notifications")
def send_notification_emails(job: Job) -> int:
    """Email unread notifications as one digest per user."""

    from django.conf import settings as django_settings
    from django.core.mail import send_mail

    from omacrm.core.models import Notification, Preferences

    try:
        from constance import config

        if not getattr(config, "notification_email_enabled", True):
            return 0
    except Exception:  # noqa: BLE001 - constance may be unavailable
        pass

    pending = (
        Notification.objects.filter(read=False, email_is_processed=False)
        .select_related("user")
        .order_by("user_id", "-created_at")
    )

    by_user: dict[int, list[Notification]] = {}
    for notification in pending:
        by_user.setdefault(notification.user_id, []).append(notification)

    sent = 0
    processed = []
    for items in by_user.values():
        user = items[0].user
        processed.extend(item.pk for item in items)

        if user is None or not user.email:
            continue
        preferences = Preferences.objects.filter(user=user).first()
        options = (preferences.notifications_config if preferences else {}) or {}
        if options.get("email") is False:
            continue

        lines = [f"- {item.message or item.get_type_display()}" for item in items]
        body = "Unread notifications in OmaCRM:\n\n" + "\n".join(lines)
        body += "\n\nOpen the admin to review them."
        send_mail(
            "OmaCRM notifications",
            body,
            django_settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True,
        )
        sent += 1

    if processed:
        Notification.objects.filter(pk__in=processed).update(email_is_processed=True)
    return sent
