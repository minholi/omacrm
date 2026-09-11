import hashlib
import hmac
import json
import urllib.request
from datetime import date, datetime, time
from decimal import Decimal

from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from omacrm.core.metadata.registry import registry
from omacrm.core.models import Webhook, WebhookQueueItem
from omacrm.core.services.jobs import jobs

MAX_ATTEMPTS = 3


def _json_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if hasattr(value, "amount") and hasattr(value, "currency"):
        return str(value)
    return str(value)


def build_payload(instance, event: str) -> dict:
    entity_type = registry.entity_type_for_instance(instance)
    data = {}
    for field in instance._meta.concrete_fields:
        data[field.name] = _json_value(getattr(instance, field.attname, None))
    return {
        "event": event,
        "entity_type": entity_type,
        "id": instance.pk,
        "data": data,
    }


def enqueue_event(instance, event: str) -> int:
    entity_type = registry.entity_type_for_instance(instance)
    if not entity_type:
        return 0

    webhooks = Webhook.objects.filter(
        entity_type=entity_type, event=event, is_active=True
    )
    payload = None
    created = 0
    for webhook in webhooks:
        if payload is None:
            payload = build_payload(instance, event)
        WebhookQueueItem.objects.create(webhook=webhook, payload=payload)
        created += 1
    return created


@jobs.register("core.process_webhooks", name="Deliver pending webhooks")
def process_webhooks(job):
    items = list(
        WebhookQueueItem.objects.filter(status=WebhookQueueItem.Status.PENDING)
        .select_related("webhook")[:100]
    )

    delivered = 0
    for item in items:
        body = json.dumps(item.payload, cls=DjangoJSONEncoder).encode()
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "OmaCRM-Webhook/1.0",
        }
        if item.webhook.secret:
            signature = hmac.new(
                item.webhook.secret.encode(), body, hashlib.sha256
            ).hexdigest()
            headers["X-Webhook-Signature"] = signature

        request = urllib.request.Request(
            item.webhook.url, data=body, headers=headers, method="POST"
        )
        item.attempts += 1
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                item.response_code = response.status
            item.status = WebhookQueueItem.Status.SENT
            item.delivered_at = timezone.now()
            item.last_error = ""
            delivered += 1
        except Exception as exc:  # noqa: BLE001 - persist delivery failure
            item.response_code = getattr(exc, "code", None)
            item.last_error = str(exc)
            if item.attempts >= MAX_ATTEMPTS:
                item.status = WebhookQueueItem.Status.FAILED
        item.save(
            update_fields=[
                "status",
                "attempts",
                "response_code",
                "last_error",
                "delivered_at",
            ]
        )
    return delivered
