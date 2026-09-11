"""Sales analytics for the dashboard."""

from datetime import date, timedelta

from constance import config
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.utils.formats import date_format, number_format

from omacrm.core.services.acl import AclService
from omacrm.crm.models import Opportunity
from omacrm.crm.models.sales import OpportunityStage

CLOSED_STAGES = {OpportunityStage.CLOSED_WON, OpportunityStage.CLOSED_LOST}


def _month_starts(months, today=None):
    current = today or date.today()
    first = date(current.year, current.month, 1)
    starts = [first]
    for _ in range(max(months - 1, 0)):
        first = (first - timedelta(days=1)).replace(day=1)
        starts.append(first)
    return list(reversed(starts))


def _as_date(value):
    return value.date() if hasattr(value, "date") else value


def format_compact(value):
    """Compact amount for dashboard labels: 97440 -> 97.4K, 1200000 -> 1.2M."""

    number = float(value or 0)
    for threshold, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if abs(number) >= threshold:
            scaled = number_format(number / threshold, decimal_pos=1)
            return f"{scaled.rstrip('0').rstrip('.')}{suffix}"
    return number_format(number, decimal_pos=0, force_grouping=True)


def _scoped(user, queryset):
    scoped = AclService.scope_queryset(user, "Opportunity", queryset)
    return Opportunity.objects.filter(pk__in=scoped.values("pk"))


def _monthly_totals(queryset, field, months):
    rows = (
        queryset.filter(close_date__isnull=False)
        .annotate(month=TruncMonth("close_date"))
        .values("month")
        .annotate(total=Sum(field))
    )
    totals = {}
    for row in rows:
        if row["month"] is None:
            continue
        totals[_as_date(row["month"])] = row["total"] or 0
    return [float(totals.get(month, 0)) for month in months]


def sales_by_month(user, *, months=12, today=None):
    """Won revenue and weighted pipeline per month, ACL-scoped."""

    months_starts = _month_starts(months, today)
    start = months_starts[0]

    won_queryset = _scoped(
        user,
        Opportunity.objects.filter(
            stage=OpportunityStage.CLOSED_WON, close_date__gte=start
        ),
    )
    pipeline_queryset = _scoped(
        user,
        Opportunity.objects.exclude(stage__in=CLOSED_STAGES).filter(
            close_date__gte=start
        ),
    )

    won = _monthly_totals(won_queryset, "amount_converted", months_starts)
    weighted = _monthly_totals(pipeline_queryset, "amount_weighted", months_starts)

    return {
        "labels": [date_format(month, "M Y") for month in months_starts],
        "won": won,
        "weighted": weighted,
        "won_total": sum(won),
        "pipeline_total": sum(weighted),
        "won_display": format_compact(sum(won)),
        "pipeline_display": format_compact(sum(weighted)),
        "currency": config.base_currency,
    }
