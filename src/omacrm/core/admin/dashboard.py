import json

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from omacrm.core.services.acl import AclService


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


def _scoped_count(user, entity_type, model, queryset=None):
    scoped = AclService.scope_queryset(
        user, entity_type, queryset if queryset is not None else model.objects.all()
    )
    return model.objects.filter(pk__in=scoped.values("pk")).count()


def _sales_context(user, context):
    from omacrm.crm.services.analytics import sales_by_month

    sales = sales_by_month(user)
    chart = {
        "labels": sales["labels"],
        "datasets": [
            {
                "type": "bar",
                "label": str(_("Closed won")),
                "data": sales["won"],
                "backgroundColor": "var(--color-primary-500)",
                "borderRadius": 8,
            },
            {
                "type": "line",
                "label": str(_("Weighted pipeline")),
                "data": sales["weighted"],
                "borderColor": "var(--color-orange-500)",
                "backgroundColor": "transparent",
                "borderWidth": 2,
                "tension": 0.35,
                "pointRadius": 0,
            },
        ],
    }
    options = {
        "responsive": True,
        "maintainAspectRatio": False,
        "maxBarThickness": 26,
        "plugins": {
            "legend": {
                "display": True,
                "position": "bottom",
                "labels": {
                    "color": "#9ca3af",
                    "usePointStyle": True,
                    "boxWidth": 8,
                    "boxHeight": 8,
                },
            }
        },
        "scales": {
            "x": {"grid": {"display": False}},
            "y": {
                "beginAtZero": True,
                "ticks": {
                    "format": {"notation": "compact", "maximumFractionDigits": 1}
                },
            },
        },
    }
    context.update(
        {
            "sales_chart": json.dumps(chart, separators=(",", ":")),
            "sales_chart_options": json.dumps(options, separators=(",", ":")),
            "sales_totals": {
                "won": sales["won_total"],
                "pipeline": sales["pipeline_total"],
                "won_display": sales["won_display"],
                "pipeline_display": sales["pipeline_display"],
                "currency": sales["currency"],
            },
        }
    )


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

        open_leads = Lead.objects.exclude(
            status__in=["Converted", "Dead", "Recycled"]
        )
        open_opportunities = Opportunity.objects.exclude(
            stage__in=["Closed Won", "Closed Lost"]
        )
        kpis.extend(
            [
                {
                    "label": _("Accounts"),
                    "value": _scoped_count(request.user, "Account", Account),
                    "icon": "domain",
                    "link": reverse("admin:crm_account_changelist"),
                },
                {
                    "label": _("Contacts"),
                    "value": _scoped_count(request.user, "Contact", Contact),
                    "icon": "contacts",
                    "link": reverse("admin:crm_contact_changelist"),
                },
                {
                    "label": _("Open leads"),
                    "value": _scoped_count(
                        request.user, "Lead", Lead, open_leads
                    ),
                    "icon": "person_add",
                    "link": reverse("admin:crm_lead_changelist"),
                },
                {
                    "label": _("Open opportunities"),
                    "value": _scoped_count(
                        request.user, "Opportunity", Opportunity, open_opportunities
                    ),
                    "icon": "trending_up",
                    "link": reverse("admin:crm_opportunity_changelist"),
                },
            ]
        )
        _sales_context(request.user, context)
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
