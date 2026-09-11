"""Recurring events: expand a rule on a Call/Meeting into occurrence records.

``recurrence_rule`` is a small structured JSON object::

    {"frequency": "weekly", "interval": 1, "weekdays": [0, 2], "count": 10}
    {"frequency": "daily", "interval": 1, "until": "2026-12-31"}

The ``frequency`` may be ``daily``, ``weekly`` or ``monthly``. Occurrences are
materialized as real records sharing the master's ``recurrence_uid``, so the
calendar renders them like normal events.
"""

import calendar
import uuid
from datetime import date, datetime, timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

FREQUENCIES = {"daily", "weekly", "monthly"}
HORIZON_DAYS = 90
MAX_COUNT = 100

COPY_EXCLUDE = {
    "id",
    "created_at",
    "modified_at",
    "created_by",
    "modified_by",
    "deleted",
    "custom_data",
    "parent_type",
    "parent_id",
    "date_start",
    "date_end",
    "recurrence_rule",
    "recurrence_uid",
}


def _parse_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError({"recurrence_rule": "Invalid until date"}) from exc


def validate_rule(rule) -> dict:
    if not isinstance(rule, dict):
        raise ValidationError({"recurrence_rule": "Rule must be a JSON object"})

    frequency = rule.get("frequency")
    if frequency not in FREQUENCIES:
        raise ValidationError(
            {"recurrence_rule": "frequency must be daily, weekly or monthly"}
        )

    try:
        interval = int(rule.get("interval", 1))
    except (TypeError, ValueError) as exc:
        raise ValidationError({"recurrence_rule": "interval must be a number"}) from exc
    if interval < 1:
        raise ValidationError({"recurrence_rule": "interval must be >= 1"})

    weekdays = rule.get("weekdays") or []
    if weekdays and (
        not isinstance(weekdays, list)
        or any(
            not isinstance(day, int) or day < 0 or day > 6 for day in weekdays
        )
    ):
        raise ValidationError({"recurrence_rule": "weekdays must be 0..6"})

    count = rule.get("count")
    if count is not None:
        try:
            count = int(count)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                {"recurrence_rule": "count must be a number"}
            ) from exc
        if count < 1:
            raise ValidationError({"recurrence_rule": "count must be >= 1"})

    until = _parse_date(rule["until"]) if rule.get("until") else None
    return {
        "frequency": frequency,
        "interval": interval,
        "weekdays": sorted(set(weekdays)) if weekdays else [],
        "count": count,
        "until": until,
    }


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def occurrences(rule: dict, start: datetime, horizon: datetime):
    """Yield occurrence datetimes, including the master's own start."""

    if start is None:
        return
    normalized = validate_rule(rule)
    frequency = normalized["frequency"]
    interval = normalized["interval"]
    count = normalized["count"]
    until = normalized["until"]

    results = []
    if frequency == "weekly" and normalized["weekdays"]:
        week_start = start - timedelta(days=start.weekday())
        week = 0
        while len(results) < MAX_COUNT:
            for weekday in normalized["weekdays"]:
                moment = (week_start + timedelta(weeks=week * interval)).replace(
                    hour=start.hour,
                    minute=start.minute,
                    second=start.second,
                    microsecond=start.microsecond,
                ) + timedelta(days=weekday)
                if moment < start:
                    continue
                if until and moment.date() > until:
                    return results
                if count and len(results) >= count:
                    return results
                if moment > horizon:
                    return results
                results.append(moment)
            week += 1
        return results

    index = 0
    while len(results) < MAX_COUNT:
        if count and index >= count:
            break
        if frequency == "daily":
            moment = start + timedelta(days=interval * index)
        elif frequency == "weekly":
            moment = start + timedelta(weeks=interval * index)
        else:
            moment = _add_months(start, interval * index)

        if until and moment.date() > until:
            break
        if index > 0 and moment > horizon:
            break
        results.append(moment)
        index += 1

    return results


def sync_occurrences(event, remove_only: bool = False) -> int:
    """Rebuild the occurrence records for a recurring event."""

    model = type(event)
    uid = event.recurrence_uid
    if not uid and event.recurrence_rule and event.pk:
        uid = uuid.uuid4().hex
        model.objects.filter(pk=event.pk).update(recurrence_uid=uid)
        event.recurrence_uid = uid

    if not uid:
        return 0

    model.objects.filter(recurrence_uid=uid).exclude(pk=event.pk).hard_delete()

    if remove_only or not event.recurrence_rule or not event.date_start:
        return 0

    rule = validate_rule(event.recurrence_rule)
    horizon = timezone.now() + timedelta(days=HORIZON_DAYS)

    duration = event.duration
    if not duration and event.date_start and event.date_end:
        duration = int((event.date_end - event.date_start).total_seconds())

    created = 0
    for index, moment in enumerate(occurrences(rule, event.date_start, horizon)):
        if index == 0:
            continue

        child = model(recurrence_uid=uid, recurrence_rule={})
        for field in event._meta.concrete_fields:
            if field.name in COPY_EXCLUDE:
                continue
            setattr(child, field.attname, getattr(event, field.attname))
        child.custom_data = dict(event.custom_data or {})
        child.date_start = moment
        child.date_end = (
            moment + timedelta(seconds=duration)
            if duration and event.date_end
            else None
        )
        if event.parent_id:
            child.parent_type = event.parent_type
            child.parent_id = event.parent_id
        child.save()
        created += 1

    return created
