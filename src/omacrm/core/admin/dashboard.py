from django.urls import reverse
from django.utils.translation import gettext_lazy as _


def environment_callback(request):
    from django.conf import settings

    if settings.DEBUG:
        return (_("Development"), "warning")
    return None


def unread_notifications_badge(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return None
    from omacrm.core.models import Notification

    return Notification.objects.filter(user=request.user, read=False).count()


def dashboard_callback(request, context):
    from omacrm.core.models import Job, Note, Notification, Team, User

    kpis = [
        {
            "label": _("Active users"),
            "value": User.objects.filter(is_active=True).count(),
            "icon": "person",
            "link": reverse("admin:core_user_changelist"),
        },
        {
            "label": _("Teams"),
            "value": Team.objects.count(),
            "icon": "groups",
            "link": reverse("admin:core_team_changelist"),
        },
        {
            "label": _("Pending jobs"),
            "value": Job.objects.filter(status=Job.Status.PENDING).count(),
            "icon": "pending_actions",
            "link": reverse("admin:core_job_changelist"),
        },
        {
            "label": _("Unread notifications"),
            "value": Notification.objects.filter(read=False).count(),
            "icon": "notifications",
            "link": reverse("admin:core_notification_changelist"),
        },
    ]

    try:
        from omacrm.crm.models import Account, Contact, Lead, Opportunity

        open_opportunities = Opportunity.objects.exclude(
            stage__in=["Closed Won", "Closed Lost"]
        )
        kpis.extend(
            [
                {
                    "label": _("Accounts"),
                    "value": Account.objects.count(),
                    "icon": "domain",
                    "link": reverse("admin:crm_account_changelist"),
                },
                {
                    "label": _("Contacts"),
                    "value": Contact.objects.count(),
                    "icon": "contacts",
                    "link": reverse("admin:crm_contact_changelist"),
                },
                {
                    "label": _("Open leads"),
                    "value": Lead.objects.exclude(
                        status__in=["Converted", "Dead", "Recycled"]
                    ).count(),
                    "icon": "person_add",
                    "link": reverse("admin:crm_lead_changelist"),
                },
                {
                    "label": _("Open opportunities"),
                    "value": open_opportunities.count(),
                    "icon": "trending_up",
                    "link": reverse("admin:crm_opportunity_changelist"),
                },
            ]
        )
    except ImportError:
        pass

    context.update(
        {
            "kpis": kpis,
            "recent_notes": Note.objects.select_related("created_by", "parent_type")[:10],
            "unread_notifications": Notification.objects.filter(
                user=request.user, read=False
            ).select_related("related_type")[:8],
        }
    )
    return context
