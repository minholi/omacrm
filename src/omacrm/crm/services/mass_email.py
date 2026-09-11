from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.db.models import F
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags

from omacrm.core.models import Note
from omacrm.core.services.jobs import jobs, schedule
from omacrm.crm.models import (
    Campaign,
    CampaignLogRecord,
    EmailQueueItem,
    MassEmail,
)
from omacrm.crm.services.email import render_email_template

UNSUBSCRIBE_SALT = "omacrm.mass_email.unsubscribe"


def unsubscribe_token(queue_item: EmailQueueItem) -> str:
    return signing.dumps({"id": queue_item.pk}, salt=UNSUBSCRIBE_SALT)


def unsubscribe_url(queue_item: EmailQueueItem, base_url: str = "") -> str:
    path = reverse("mass_email_unsubscribe", args=[unsubscribe_token(queue_item)])
    return f"{base_url.rstrip('/')}{path}" if base_url else path


def unsubscribe(queue_item: EmailQueueItem) -> bool:
    """Opt the recipient out of the mass email's target lists."""

    from omacrm.crm.services.target_lists import set_opt_out

    record = queue_item.entity
    if record is None:
        return False

    for target_list in queue_item.mass_email.target_lists.all():
        set_opt_out(record, target_list, opted_out=True)

    mass_email = queue_item.mass_email
    if mass_email.campaign_id:
        CampaignLogRecord.objects.create(
            campaign=mass_email.campaign,
            action=CampaignLogRecord.Action.OPTED_OUT,
            entity=record,
            data={"email": queue_item.email_address},
        )
        Campaign.objects.filter(pk=mass_email.campaign_id).update(
            opted_out_count=F("opted_out_count") + 1
        )
    return True


def build_queue(mass_email: MassEmail) -> int:
    """Expand target lists minus opted-out members into queue items."""

    EmailQueueItem.objects.filter(
        mass_email=mass_email, status=EmailQueueItem.Status.PENDING
    ).delete()

    seen = set()
    created = 0
    for target_list in mass_email.target_lists.all():
        for member in target_list.members.filter(opted_out=False):
            record = member.entity
            if record is None:
                continue
            email = getattr(record, "email_address", "") or ""
            if not email:
                continue
            key = (member.entity_type_id, member.entity_id)
            if key in seen:
                continue
            seen.add(key)
            EmailQueueItem.objects.create(
                mass_email=mass_email,
                entity=record,
                email_address=email,
            )
            created += 1

    mass_email.status = (
        MassEmail.Status.IN_PROCESS if created else MassEmail.Status.FAILED
    )
    mass_email.save(update_fields=["status"])
    return created


@jobs.register("crm.process_mass_email", name="Process mass email queue")
def process_mass_email(job):
    mass_email_id = job.data.get("mass_email_id")
    batch_size = int(job.data.get("batch_size", 50))
    mass_email = MassEmail.objects.filter(pk=mass_email_id).first()
    if mass_email is None:
        return 0
    if mass_email.status not in {
        MassEmail.Status.IN_PROCESS,
        MassEmail.Status.PENDING,
    }:
        return 0

    items = list(
        EmailQueueItem.objects.filter(
            mass_email=mass_email, status=EmailQueueItem.Status.PENDING
        )[:batch_size]
    )

    sent = 0
    for item in items:
        item.attempt_count += 1
        try:
            record = item.entity
            if record is None:
                raise ValueError("Target record no longer exists")
            if mass_email.email_template_id is None:
                raise ValueError("No email template selected")

            subject, body = render_email_template(mass_email.email_template, record)
            opt_out_url = unsubscribe_url(item)
            body = f'{body}\n<p><a href="{opt_out_url}">{opt_out_url}</a></p>'
            send_mail(
                subject,
                strip_tags(body),
                mass_email.from_address or settings.DEFAULT_FROM_EMAIL,
                [item.email_address],
                html_message=body,
                fail_silently=False,
            )
            item.status = EmailQueueItem.Status.SENT
            item.sent_at = timezone.now()
            item.last_error = ""
            item.save(
                update_fields=["status", "sent_at", "last_error", "attempt_count"]
            )
            sent += 1

            if mass_email.campaign_id:
                CampaignLogRecord.objects.create(
                    campaign=mass_email.campaign,
                    action=CampaignLogRecord.Action.SENT,
                    entity=record,
                    data={"email": item.email_address},
                )
                Campaign.objects.filter(pk=mass_email.campaign_id).update(
                    sent_count=F("sent_count") + 1
                )
            if mass_email.store_sent_emails:
                Note.objects.create(
                    type=Note.Type.EMAIL,
                    parent=record,
                    post=subject,
                    data={"to": item.email_address, "subject": subject},
                )
        except Exception as exc:  # noqa: BLE001 - keep the queue moving
            item.status = EmailQueueItem.Status.FAILED
            item.last_error = str(exc)
            item.save(update_fields=["status", "last_error", "attempt_count"])

    if EmailQueueItem.objects.filter(
        mass_email=mass_email, status=EmailQueueItem.Status.PENDING
    ).exists():
        schedule(
            "crm.process_mass_email",
            data={"mass_email_id": mass_email.pk},
            name=f"Mass email: {mass_email.name}",
            execute_time=timezone.now() + timedelta(minutes=1),
        )
    else:
        mass_email.status = MassEmail.Status.COMPLETE
        mass_email.save(update_fields=["status"])

    return sent
