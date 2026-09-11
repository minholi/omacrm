"""Collaboration demo data: notes, attachments, reactions, notifications."""

from omacrm.core.models import (
    Attachment,
    Notification,
    StreamEvent,
    UserReaction,
    Webhook,
    WebhookQueueItem,
)
from omacrm.core.services import notifications, stream

from .common import moment_in, text_file


def seed_collaboration(context):
    webhook, _ = Webhook.objects.get_or_create(
        name="Demo lead webhook",
        entity_type="Lead",
        event="create",
        url="https://example.com/hooks/leads",
        defaults={"secret": "demo-webhook-secret", "is_active": True},
    )
    if webhook.queue_items.count() == 0:
        payload = {
            "entity_type": "Lead",
            "event": "create",
            "data": {"name": "Aisha Rahman", "status": "New", "source": "Web Site"},
        }
        WebhookQueueItem.objects.create(
            webhook=webhook, payload=payload, status="Pending"
        )
        WebhookQueueItem.objects.create(
            webhook=webhook,
            payload=payload,
            status="Sent",
            attempts=1,
            response_code=200,
            delivered_at=moment_in(-1, 10),
        )
        WebhookQueueItem.objects.create(
            webhook=webhook,
            payload=payload,
            status="Failed",
            attempts=3,
            last_error="Connection timeout",
        )

    opportunity = context["opportunities"][0]
    account = context["accounts"]["TechBrasil Sistemas"]
    contact = context["contacts"]["john.carter@northwind.example"]

    note = stream.post_note(
        opportunity,
        "Kickoff scheduled. @demo @bruno please review the proposal before Friday.",
        user=context["ana"],
    )
    note_account = stream.post_note(
        account,
        "Contract signed and filed under Contracts.",
        user=context["demo"],
    )
    note_internal = stream.post_note(
        contact,
        "Internal: keep an eye on the renewal date.",
        user=context["demo"],
        is_internal=True,
    )

    from django.contrib.contenttypes.models import ContentType

    account_ct = ContentType.objects.get_for_model(
        account, for_concrete_model=False
    )
    attachment, _ = Attachment.objects.get_or_create(
        name="renewal-checklist.txt",
        related_type=account_ct,
        related_id=account.pk,
        defaults={"mime_type": "text/plain"},
    )
    if not attachment.file:
        attachment.file.save(
            "renewal-checklist.txt",
            text_file("renewal-checklist.txt", "1. Confirm budget\n2. Review terms\n"),
            save=True,
        )
    note_account.attachments.add(attachment)

    for target_note, user, emoji in (
        (note, context["demo"], "👍"),
        (note, context["bruno"], "👍"),
        (note_account, context["ana"], "🎉"),
        (note_account, context["demo"], "❤️"),
        (note_internal, context["carla"], "👀"),
    ):
        UserReaction.objects.get_or_create(note=target_note, user=user, emoji=emoji)

    notifications.notify(
        context["demo"],
        Notification.Type.ASSIGNMENT,
        message="You were assigned to Northwind ERP rollout.",
        related=opportunity,
    )
    notifications.notify(
        context["ana"],
        Notification.Type.SYSTEM,
        message="Case 'Data import mapping issue' needs your review.",
        related=context["cases"][4],
    )
    notifications.notify(
        context["carla"],
        Notification.Type.ASSIGNMENT,
        message="A portal case was assigned to you.",
        related=context["cases"][0],
    )
    read_notification = notifications.notify(
        context["demo"],
        Notification.Type.STREAM,
        message="Bruno updated the BlueWave deal.",
        related=context["opportunities"][3],
    )
    if read_notification is not None and not read_notification.read:
        read_notification.read = True
        read_notification.save(update_fields=["read"])

    if not StreamEvent.objects.filter(user=context["demo"], note=note).exists():
        StreamEvent.objects.create(
            user=context["demo"],
            note=note,
            message="Ana mentioned you in a note on Northwind ERP rollout.",
        )

    context.update({"webhook": webhook})
