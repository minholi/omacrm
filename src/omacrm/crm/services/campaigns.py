"""Campaign statistics: revenue recalculation and bounce recording."""

from decimal import Decimal

from django.db.models import F, Sum

from omacrm.crm.models import (
    Campaign,
    CampaignLogRecord,
    EmailQueueItem,
    Opportunity,
    OpportunityStage,
)

BOUNCE_TYPES = {"Hard", "Soft"}


def recalc_revenue(campaign: Campaign) -> Decimal:
    """Set the campaign revenue to the sum of its Closed Won opportunities."""

    total = (
        Opportunity.objects.filter(
            campaign=campaign, stage=OpportunityStage.CLOSED_WON
        ).aggregate(total=Sum("amount_converted"))["total"]
        or Decimal("0")
    )
    Campaign.objects.filter(pk=campaign.pk).update(revenue=total)
    return total


def record_bounce(queue_item: EmailQueueItem, bounce_type: str):
    """Mark a queue item as bounced and log it on the campaign."""

    if bounce_type not in BOUNCE_TYPES:
        raise ValueError(f"bounce_type must be one of {sorted(BOUNCE_TYPES)}")

    queue_item.status = EmailQueueItem.Status.FAILED
    queue_item.last_error = f"{bounce_type} bounce"
    queue_item.save(update_fields=["status", "last_error"])

    mass_email = queue_item.mass_email
    if not mass_email.campaign_id:
        return None

    record = CampaignLogRecord.objects.create(
        campaign=mass_email.campaign,
        action=CampaignLogRecord.Action.BOUNCED,
        bounced_type=bounce_type,
        entity=queue_item.entity,
        data={"email": queue_item.email_address},
    )
    Campaign.objects.filter(pk=mass_email.campaign_id).update(
        bounced_count=F("bounced_count") + 1
    )
    return record
