from decimal import Decimal

from django.db.models import Max
from django.utils import timezone
from django.utils.html import strip_tags

from omacrm.core.services.currency import base_currency, convert
from omacrm.core.services.hooks import hooks
from omacrm.core.services.phone import normalize_phone
from omacrm.crm.models import (
    OPPORTUNITY_NON_CLOSED_STAGES,
    OPPORTUNITY_PROBABILITY_MAP,
    AccountContact,
    Case,
    KnowledgeBaseArticle,
    Lead,
    Opportunity,
    TaskStatus,
)
from omacrm.crm.services.reminders import sync_reminders


@hooks.register("Opportunity", "before_save")
def opportunity_stage_rules(instance, **kwargs):
    """Maintain probability and last stage when the stage changes."""

    stage_map = OPPORTUNITY_PROBABILITY_MAP
    stage = instance.stage
    default_probability = stage_map.get(stage, 0)

    old = None
    if not instance._state.adding and instance.pk:
        old = (
            Opportunity.all_objects.filter(pk=instance.pk)
            .values("stage", "probability", "last_stage")
            .first()
        )

    if old is None:
        if instance.probability is None:
            instance.probability = default_probability
        if stage in OPPORTUNITY_NON_CLOSED_STAGES:
            instance.last_stage = stage
        return

    old_stage = old["stage"]
    if old_stage != stage:
        old_default = stage_map.get(old_stage)
        if instance.probability is None or instance.probability == old_default:
            instance.probability = default_probability

        if stage in OPPORTUNITY_NON_CLOSED_STAGES:
            instance.last_stage = stage
        elif old_stage in OPPORTUNITY_NON_CLOSED_STAGES:
            instance.last_stage = old_stage

    if instance.probability is None:
        instance.probability = default_probability


@hooks.register("Opportunity", "after_save")
def opportunity_amount_weighted(instance, **kwargs):
    amount = getattr(instance, "amount", None)
    if amount is None:
        weighted = None
    else:
        amount_value = Decimal(amount.amount) if hasattr(amount, "amount") else Decimal(amount)
        probability = instance.probability or 0
        weighted = (amount_value * Decimal(probability) / Decimal(100)).quantize(
            Decimal("0.01")
        )

    if instance.amount_weighted != weighted:
        Opportunity.objects.filter(pk=instance.pk).update(amount_weighted=weighted)
        instance.amount_weighted = weighted


@hooks.register("Lead", "before_save")
def lead_converted_at(instance, **kwargs):
    if instance.status == Lead.Status.CONVERTED:
        if instance.converted_at is None:
            instance.converted_at = timezone.now()
    else:
        instance.converted_at = None


@hooks.register("Task", "before_save")
def task_date_completed(instance, **kwargs):
    if instance.status == TaskStatus.COMPLETED:
        if instance.date_completed is None:
            instance.date_completed = timezone.now()
    else:
        instance.date_completed = None


@hooks.register("Contact", "after_save")
def contact_primary_account_link(instance, **kwargs):
    """Keep the primary account in sync with the account contact relation."""

    if not instance.account_id:
        return
    AccountContact.objects.get_or_create(
        account_id=instance.account_id,
        contact=instance,
        defaults={"role": instance.title},
    )


def _update_duration(instance):
    if instance.date_start and instance.date_end:
        seconds = int((instance.date_end - instance.date_start).total_seconds())
        if seconds >= 0:
            instance.duration = seconds


@hooks.register("Call", "before_save")
def call_duration(instance, **kwargs):
    _update_duration(instance)


@hooks.register("Meeting", "before_save")
def meeting_duration(instance, **kwargs):
    _update_duration(instance)


@hooks.register("Task", "after_save")
def task_reminders(instance, **kwargs):
    sync_reminders(instance)


@hooks.register("Call", "after_save")
def call_reminders(instance, **kwargs):
    sync_reminders(instance)


@hooks.register("Meeting", "after_save")
def meeting_reminders(instance, **kwargs):
    sync_reminders(instance)


@hooks.register("Case", "before_save")
def case_number(instance, **kwargs):
    if instance.number is None:
        current = Case.all_objects.aggregate(value=Max("number"))["value"] or 0
        instance.number = current + 1


@hooks.register("KnowledgeBaseArticle", "before_save")
def knowledge_base_body_plain(instance, **kwargs):
    instance.body_plain = strip_tags(instance.body or "")


@hooks.register("Opportunity", "after_save")
def opportunity_amount_converted(instance, **kwargs):
    amount = instance.amount
    converted = None
    if amount is not None:
        value = amount.amount if hasattr(amount, "amount") else amount
        converted = convert(value, instance.amount_currency or base_currency())
    if instance.amount_converted != converted:
        Opportunity.objects.filter(pk=instance.pk).update(amount_converted=converted)
        instance.amount_converted = converted


@hooks.register("Lead", "before_save")
def lead_amount_converted(instance, **kwargs):
    amount = instance.opportunity_amount
    if amount is None:
        instance.opportunity_amount_converted = None
    else:
        value = amount.amount if hasattr(amount, "amount") else amount
        instance.opportunity_amount_converted = convert(
            value, instance.opportunity_amount_currency or base_currency()
        )


def _normalize_phone_number(instance):
    value = getattr(instance, "phone_number", None)
    if not value:
        return
    normalized = normalize_phone(value)
    if normalized:
        instance.phone_number = normalized


@hooks.register("Account", "before_save")
def account_phone_number(instance, **kwargs):
    _normalize_phone_number(instance)


@hooks.register("Contact", "before_save")
def contact_phone_number(instance, **kwargs):
    _normalize_phone_number(instance)


@hooks.register("Lead", "before_save")
def lead_phone_number(instance, **kwargs):
    _normalize_phone_number(instance)


def _sync_event_recurrence(instance) -> None:
    from omacrm.crm.services.recurrence import sync_occurrences

    if getattr(instance, "_recurrence_syncing", False):
        return

    instance._recurrence_syncing = True
    try:
        if getattr(instance, "deleted", False):
            sync_occurrences(instance, remove_only=True)
        elif instance.recurrence_rule:
            sync_occurrences(instance)
    finally:
        instance._recurrence_syncing = False


@hooks.register("Call", "after_save")
def call_recurrence(instance, **kwargs):
    _sync_event_recurrence(instance)


@hooks.register("Meeting", "after_save")
def meeting_recurrence(instance, **kwargs):
    _sync_event_recurrence(instance)
