"""Marketing demo data: target lists, campaigns, mass email, lead capture."""

from omacrm.crm.models import (
    Campaign,
    CampaignLogRecord,
    CampaignTrackingUrl,
    EmailQueueItem,
    LeadCapture,
    MassEmail,
    TargetList,
    TargetListCategory,
)
from omacrm.crm.services.campaigns import recalc_revenue
from omacrm.crm.services.target_lists import add_to_target_list

from .common import date_in, moment_in

CAMPAIGNS = (
    ("September Newsletter", "Complete", "Newsletter", -60, -30),
    ("Black Friday Webinar", "Active", "Web", -10, 20),
    ("Product Launch Q4", "Planning", "Informational Email", 20, 60),
)


def seed_marketing(context):
    categories = {}
    for name in ("Newsletter", "Events"):
        category, _ = TargetListCategory.objects.get_or_create(name=name)
        categories[name] = category

    newsletter_list, _ = TargetList.objects.get_or_create(
        name="Newsletter Subscribers",
        defaults={"description": "Contacts opted in to the newsletter.", "category": categories["Newsletter"]},
    )
    leads_list, _ = TargetList.objects.get_or_create(
        name="Q3 Leads",
        defaults={"description": "Leads from the Q3 campaign.", "category": categories["Events"]},
    )

    contact_items = list(context["contacts"].values())[:10]
    lead_items = list(context["leads"])[:8]
    for index, contact in enumerate(contact_items):
        add_to_target_list(contact, newsletter_list, opted_out=index == 3)
    for index, lead in enumerate(lead_items):
        add_to_target_list(lead, leads_list, opted_out=index == 2)

    campaigns = {}
    for name, status, campaign_type, start, end in CAMPAIGNS:
        campaign, _ = Campaign.objects.get_or_create(
            name=name,
            defaults={
                "status": status,
                "type": campaign_type,
                "description": f"Demo campaign: {name}.",
                "assigned_user": context["demo"],
            },
        )
        campaign.start_date = date_in(start)
        campaign.end_date = date_in(end)
        campaign.save(update_fields=["start_date", "end_date"])
        campaigns[name] = campaign

    campaigns["September Newsletter"].target_lists.add(newsletter_list)
    campaigns["Black Friday Webinar"].target_lists.add(newsletter_list, leads_list)

    tracking, _ = CampaignTrackingUrl.objects.get_or_create(
        campaign=campaigns["Black Friday Webinar"],
        name="Webinar landing page",
        defaults={"url": "https://example.com/webinar", "action": "Redirect"},
    )
    CampaignTrackingUrl.objects.get_or_create(
        campaign=campaigns["Black Friday Webinar"],
        name="Thank you message",
        defaults={"action": "Show Message", "message": "Thanks for registering!"},
    )

    if campaigns["September Newsletter"].log_records.count() == 0:
        campaign = campaigns["September Newsletter"]
        for index in range(8):
            record = contact_items[index % len(contact_items)]
            CampaignLogRecord.objects.create(
                campaign=campaign,
                action="Sent",
                action_date=moment_in(-40 + index, 10),
                entity=record,
            )
        for index in range(5):
            CampaignLogRecord.objects.create(
                campaign=campaign,
                action="Opened",
                action_date=moment_in(-38 + index, 12),
                entity=contact_items[index],
            )
        for index in range(3):
            CampaignLogRecord.objects.create(
                campaign=campaign,
                action="Clicked",
                action_date=moment_in(-36 + index, 14),
                entity=contact_items[index],
            )
        CampaignLogRecord.objects.create(
            campaign=campaign,
            action="Opted Out",
            action_date=moment_in(-35, 15),
            entity=contact_items[3],
        )
        CampaignLogRecord.objects.create(
            campaign=campaign,
            action="Bounced",
            bounced_type="Hard",
            action_date=moment_in(-39, 9),
            entity=contact_items[5],
        )
        CampaignLogRecord.objects.create(
            campaign=campaign,
            action="Lead Created",
            action_date=moment_in(-34, 11),
            entity=lead_items[0],
        )

        campaign.sent_count = 8
        campaign.opened_count = 5
        campaign.clicked_count = 3
        campaign.opted_out_count = 1
        campaign.bounced_count = 1
        campaign.save(
            update_fields=[
                "sent_count",
                "opened_count",
                "clicked_count",
                "opted_out_count",
                "bounced_count",
            ]
        )

        active = campaigns["Black Friday Webinar"]
        for index in range(10):
            record = (contact_items + lead_items)[index % (len(contact_items) + len(lead_items))]
            CampaignLogRecord.objects.create(
                campaign=active,
                action="Sent",
                action_date=moment_in(-8 + (index // 3), 10),
                entity=record,
            )
        for index in range(4):
            CampaignLogRecord.objects.create(
                campaign=active,
                action="Opened",
                action_date=moment_in(-6 + index, 13),
                entity=contact_items[index],
            )
        CampaignLogRecord.objects.create(
            campaign=active,
            action="Clicked",
            action_date=moment_in(-5, 16),
            entity=contact_items[0],
        )
        active.sent_count = 10
        active.opened_count = 4
        active.clicked_count = 1
        active.save(update_fields=["sent_count", "opened_count", "clicked_count"])

    won = [
        opportunity
        for opportunity in context["opportunities"]
        if opportunity.name in {"GreenLeaf supply chain", "Copacabana travel portal"}
    ]
    if won:
        for opportunity in won:
            opportunity.campaign = campaigns["September Newsletter"]
            opportunity.save(update_fields=["campaign"])
        recalc_revenue(campaigns["September Newsletter"])

    templates = context["email_templates"]
    mass_email, _ = MassEmail.objects.get_or_create(
        name="September Newsletter delivery",
        defaults={
            "status": "Complete",
            "from_name": "OmaCRM Team",
            "from_address": "news@example.com",
            "reply_to_address": "support@example.com",
            "start_at": moment_in(-60, 8),
            "email_template": templates["Newsletter"],
            "campaign": campaigns["September Newsletter"],
            "assigned_user": context["demo"],
        },
    )
    mass_email.target_lists.add(newsletter_list)
    if mass_email.queue_items.count() == 0:
        for index, contact in enumerate(contact_items[:7]):
            EmailQueueItem.objects.create(
                mass_email=mass_email,
                entity=contact,
                email_address=contact.email_address,
                status="Failed" if index == 6 else "Sent",
                attempt_count=1,
                last_error="Mailbox full" if index == 6 else "",
                sent_at=None if index == 6 else moment_in(-59, 9 + index % 5),
            )

    MassEmail.objects.get_or_create(
        name="Product Launch teaser",
        defaults={
            "status": "Draft",
            "from_name": "OmaCRM Team",
            "from_address": "news@example.com",
            "email_template": templates["Welcome"],
            "campaign": campaigns["Product Launch Q4"],
            "assigned_user": context["demo"],
        },
    )

    capture, _ = LeadCapture.objects.get_or_create(
        name="Website Demo Request",
        defaults={
            "campaign": campaigns["Product Launch Q4"],
            "target_list": leads_list,
            "source": "Campaign",
            "default_assigned_user": context["demo"],
            "field_list": ["first_name", "last_name", "email_address", "description"],
            "opt_in_confirmation": True,
            "opt_in_template": templates["Welcome"],
        },
    )

    context.update(
        {
            "target_lists": {"newsletter": newsletter_list, "leads": leads_list},
            "campaigns": campaigns,
            "mass_email": mass_email,
            "lead_capture": capture,
            "tracking_url": tracking,
        }
    )
