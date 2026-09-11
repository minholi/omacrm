"""Workflow automation: trigger → optional condition → actions."""

import contextvars
import logging

from omacrm.core.metadata.registry import registry
from omacrm.core.services.formula import build_context, evaluate

logger = logging.getLogger(__name__)

_running = contextvars.ContextVar("omacrm_workflow_running", default=False)


def _run_action(action: dict, instance) -> None:
    action_type = action.get("type")

    if action_type == "set_field":
        field = action["field"]
        setattr(instance, field, action.get("value"))
        instance.save(update_fields=[field])

    elif action_type == "notify":
        from omacrm.core.models import Notification
        from omacrm.core.services import notifications

        target = getattr(instance, "assigned_user", None)
        user_field = action.get("user_field")
        if user_field:
            target = getattr(instance, user_field, None)
        if target is not None:
            message = action.get("message") or f"Workflow triggered on {instance}"
            notifications.notify(
                target,
                Notification.Type.SYSTEM,
                message=str(message),
                related=instance,
            )

    elif action_type == "send_email":
        from django.conf import settings as django_settings
        from django.core.mail import send_mail
        from django.template import Context, Template
        from django.utils.html import strip_tags

        from omacrm.core.models import Note

        recipient = action.get("to") or "email_address"
        if hasattr(instance, recipient):
            recipient = getattr(instance, recipient)
        if not recipient:
            raise ValueError("No recipient email address")

        context = Context(
            {
                "record": instance,
                "object": instance,
                **{
                    field.name: getattr(instance, field.attname, "")
                    for field in instance._meta.fields
                },
            }
        )
        subject = Template(
            action.get("subject") or "Workflow notification"
        ).render(context)
        body = Template(action.get("body") or "").render(context)

        send_mail(
            subject,
            strip_tags(body),
            django_settings.DEFAULT_FROM_EMAIL,
            [recipient],
            html_message=body or None,
            fail_silently=False,
        )
        Note.objects.create(
            type=Note.Type.EMAIL,
            parent=instance,
            post=subject,
            data={"to": recipient, "workflow": True},
        )

    elif action_type == "webhook":
        from omacrm.core.models import Webhook, WebhookQueueItem
        from omacrm.core.services.webhooks import build_payload

        webhook = Webhook.objects.filter(
            pk=action.get("webhook_id"), is_active=True
        ).first()
        if webhook is None:
            raise ValueError(f"Unknown webhook: {action.get('webhook_id')}")

        event = action.get("event") or "update"
        WebhookQueueItem.objects.create(
            webhook=webhook, payload=build_payload(instance, event)
        )

    elif action_type == "create_record":
        entity_type = action.get("entity_type")
        if not entity_type or not registry.has(entity_type):
            raise ValueError(f"Unknown entity type: {entity_type}")
        model = registry.model_for(entity_type)
        values = action.get("values") or {}
        record = model(**values)
        record.save()
        return record

    return None


def run_workflows(instance, event: str) -> int:
    """Run matching workflow rules for a record event. Returns rules matched."""

    if _running.get():
        return 0

    entity_type = registry.entity_type_for_instance(instance)
    if not entity_type:
        return 0

    from omacrm.core.models import Workflow

    try:
        workflows = list(
            Workflow.objects.filter(
                entity_type=entity_type, event=event, is_active=True
            ).order_by("order", "id")
        )
    except Exception:  # noqa: BLE001 - DB may not be ready during setup
        return 0

    if not workflows:
        return 0

    token = _running.set(True)
    matched = 0
    try:
        for workflow in workflows:
            try:
                if workflow.condition:
                    if not bool(evaluate(workflow.condition, build_context(instance))):
                        continue
                matched += 1
                for action in workflow.actions or []:
                    _run_action(action, instance)
            except Exception:  # noqa: BLE001 - a failing rule must not break saves
                logger.exception("Workflow %s failed", workflow.pk)
    finally:
        _running.reset(token)

    return matched
