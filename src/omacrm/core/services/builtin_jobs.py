import json
import logging
from urllib.request import urlopen

from omacrm.core.models import Job
from omacrm.core.services.jobs import jobs

logger = logging.getLogger(__name__)


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


@jobs.register("core.sync_currency_rates", name="Sync currency rates")
def sync_currency_rates(job: Job) -> int:
    """Fetch today's rates from a JSON endpoint (constance currency_rates_url)."""

    from decimal import Decimal

    from django.utils import timezone

    from omacrm.core.models import Currency, CurrencyRate
    from omacrm.core.services.currency import base_currency

    try:
        from constance import config

        url = getattr(config, "currency_rates_url", "")
    except Exception:  # noqa: BLE001 - constance may be unavailable
        url = ""
    if not url:
        return 0

    try:
        with urlopen(url, timeout=15) as response:  # noqa: S310 - configured URL
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - network/parse failures are logged
        logger.exception("Failed to fetch currency rates from %s", url)
        return 0

    rates = payload.get("rates") or payload.get("conversion_rates") or {}
    base = (payload.get("base") or payload.get("base_code") or "").upper()
    target = base_currency()
    if base and base != target:
        logger.warning(
            "Currency rate payload is based on %s, expected %s; skipping", base, target
        )
        return 0

    date = timezone.localdate()
    updated = 0
    for code, value in rates.items():
        code = str(code).upper()
        if code == target:
            continue
        currency = Currency.objects.filter(code=code, is_active=True).first()
        if currency is None:
            continue
        rate = Decimal(str(value))
        CurrencyRate.objects.update_or_create(
            currency=currency, date=date, defaults={"rate": rate}
        )
        if currency.rate != rate:
            currency.rate = rate
            currency.save(update_fields=["rate", "updated_at"])
        updated += 1

    return updated
