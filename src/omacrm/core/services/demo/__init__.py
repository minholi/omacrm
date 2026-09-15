"""Rich demo dataset for showcasing OmaCRM.

``seed_all`` seeds the platform (users, teams, portal, jobs, currencies) plus
a full set of business records. All entries use stable natural keys, so
running it twice does not duplicate data; use ``reset=True`` to rebuild.
"""

from django.utils import timezone

from .common import DEFAULT_SEED
from .platform import seed_platform

RESET_MODELS = (
    "crm.EmailQueueItem",
    "crm.CampaignLogRecord",
    "crm.CampaignTrackingUrl",
    "crm.MassEmail",
    "crm.Campaign",
    "crm.TargetListMember",
    "crm.TargetList",
    "crm.TargetListCategory",
    "crm.LeadCapture",
    "crm.Attendance",
    "crm.Reminder",
    "crm.Task",
    "crm.Call",
    "crm.Meeting",
    "crm.Case",
    "crm.KnowledgeBaseArticle",
    "crm.KnowledgeBaseCategory",
    "crm.Document",
    "crm.DocumentFolder",
    "crm.OpportunityContact",
    "crm.Opportunity",
    "crm.Lead",
    "crm.AccountContact",
    "crm.Contact",
    "crm.Account",
    "core.DynamicRecord",
    "core.RecordLink",
    "core.CustomLink",
    "core.CustomEntity",
    "core.Note",
    "core.UserReaction",
    "core.StreamEvent",
    "core.Notification",
    "core.Attachment",
    "core.Email",
    "crm.EmailTemplate",
    "core.EmailAccount",
    "core.Layout",
    "core.CustomField",
    "core.Formula",
    "core.WorkflowRun",
    "core.Workflow",
    "core.WebhookQueueItem",
    "core.Webhook",
    "core.SavedFilter",
    "core.CurrencyRate",
)


def reset_demo_data() -> None:
    """Hard-delete demo business data, keeping admin/demo/portal users."""

    from django.apps import apps

    from omacrm.core.models import Attachment
    from omacrm.crm.models import Document

    for model in (Document, Attachment):
        for instance in model.objects.all():
            if instance.file:
                instance.file.delete(save=False)

    for label in RESET_MODELS:
        model = apps.get_model(label)
        manager = getattr(model, "all_objects", None) or model.objects
        manager.all().delete()

    from django.contrib.auth import get_user_model

    User = get_user_model()
    User.objects.filter(
        user_name__in=[
            "ana.souza",
            "bruno.almeida",
            "carla.mendes",
            "api.bot",
        ]
    ).delete()


def seed_all(
    *,
    stdout=None,
    reset: bool = False,
    rng_seed: int = DEFAULT_SEED,
    base_url: str = "",
    password: str = "demo12345",
    admin_password: str = "admin12345",
) -> dict:
    def log(message: str) -> None:
        if stdout is not None:
            stdout.write(message)
            stdout.flush()

    if reset:
        log("Resetting demo business data...")
        reset_demo_data()

    from omacrm.core.services.context import set_current_user

    context = seed_platform(
        password=password, admin_password=admin_password, rng_seed=rng_seed
    )
    context["base_url"] = base_url
    context["started_at"] = timezone.now()

    set_current_user(context["admin"])
    try:
        from .activities import seed_activities
        from .collaboration import seed_collaboration
        from .customization import seed_customization
        from .email import seed_email
        from .marketing import seed_marketing
        from .sales import seed_sales
        from .support import seed_support

        log("Seeding sales pipeline...")
        seed_sales(context)
        log("Seeding support (cases, knowledge base, documents)...")
        seed_support(context)
        log("Seeding activities (tasks, calls, meetings)...")
        seed_activities(context)
        log("Seeding email threads...")
        seed_email(context)
        log("Seeding marketing (target lists, campaigns, mass email)...")
        seed_marketing(context)
        log("Seeding collaboration (notes, reactions, notifications)...")
        seed_collaboration(context)
        log("Seeding customization (fields, layouts, automation)...")
        seed_customization(context)
    finally:
        set_current_user(None)

    return context
