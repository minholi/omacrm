"""Event invitations: signed accept/decline links sent by email."""

from django.conf import settings as django_settings
from django.contrib.contenttypes.models import ContentType
from django.core import signing
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from omacrm.crm.models import AcceptanceStatus, Attendance

TOKEN_SALT = "omacrm.event.invitation"
TOKEN_MAX_AGE = 60 * 60 * 24 * 30


def make_token(attendance: Attendance) -> str:
    return signing.dumps({"id": attendance.pk}, salt=TOKEN_SALT)


def confirmation_url(attendance: Attendance, action: str, base_url: str = "") -> str:
    path = reverse(
        "event_confirmation",
        args=[attendance.pk, action, make_token(attendance)],
    )
    return f"{base_url.rstrip('/')}{path}" if base_url else path


def send_invitations(event, base_url: str = "") -> int:
    """Email accept/decline links to all attendees with an address."""

    content_type = ContentType.objects.get_for_model(
        type(event), for_concrete_model=False
    )
    attendances = Attendance.objects.filter(
        event_type=content_type, event_id=event.pk
    ).select_related("user", "contact", "lead")

    sent = 0
    for attendance in attendances:
        email = attendance.email
        if not email:
            continue

        accept = confirmation_url(attendance, "accept", base_url)
        decline = confirmation_url(attendance, "decline", base_url)
        when = event.date_start.strftime("%Y-%m-%d %H:%M") if event.date_start else ""

        body = (
            f"You are invited to: {event.name}\n"
            f"When: {when}\n\n"
            f"Accept: {accept}\n"
            f"Decline: {decline}\n"
        )
        send_mail(
            f"Invitation: {event.name}",
            body,
            django_settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=True,
        )
        attendance.invitation_sent_at = timezone.now()
        attendance.save(update_fields=["invitation_sent_at"])
        sent += 1

    return sent


def confirm_attendance(attendance_id: int, action: str, token: str):
    """Validate a signed link and update the attendance status."""

    if action not in {"accept", "decline"}:
        return None

    try:
        data = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
    except signing.BadSignature:
        return None

    if data.get("id") != attendance_id:
        return None

    attendance = Attendance.objects.filter(pk=attendance_id).first()
    if attendance is None:
        return None

    attendance.status = (
        AcceptanceStatus.ACCEPTED if action == "accept" else AcceptanceStatus.DECLINED
    )
    attendance.save(update_fields=["status"])
    return attendance
