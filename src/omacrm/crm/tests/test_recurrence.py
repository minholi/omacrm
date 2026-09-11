from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from omacrm.crm.models import Call
from omacrm.crm.services.recurrence import (
    occurrences,
    sync_occurrences,
    validate_rule,
)

START = timezone.make_aware(datetime(2026, 1, 5, 9, 0))  # Monday


class RuleValidationTests(TestCase):
    def test_valid_rule_is_normalized(self):
        rule = validate_rule(
            {"frequency": "weekly", "interval": "2", "weekdays": [0, 2, 2]}
        )
        self.assertEqual(rule["interval"], 2)
        self.assertEqual(rule["weekdays"], [0, 2])

    def test_invalid_rules(self):
        for rule in (
            "not-a-dict",
            {"frequency": "yearly"},
            {"frequency": "daily", "interval": 0},
            {"frequency": "weekly", "weekdays": [9]},
            {"frequency": "daily", "count": 0},
            {"frequency": "daily", "until": "not-a-date"},
        ):
            with self.assertRaises(ValidationError, msg=rule):
                validate_rule(rule)


class OccurrenceTests(TestCase):
    def test_daily_interval(self):
        result = occurrences(
            {"frequency": "daily", "interval": 2, "count": 3},
            START,
            START + timedelta(days=30),
        )
        self.assertEqual(
            result,
            [START, START + timedelta(days=2), START + timedelta(days=4)],
        )

    def test_weekly_weekdays(self):
        result = occurrences(
            {"frequency": "weekly", "weekdays": [0, 2], "count": 3},
            START,
            START + timedelta(days=60),
        )
        self.assertEqual(
            result,
            [START, START + timedelta(days=2), START + timedelta(days=7)],
        )

    def test_monthly_clamps_day(self):
        end_of_month = timezone.make_aware(datetime(2026, 1, 31, 10, 0))
        result = occurrences(
            {"frequency": "monthly", "count": 3},
            end_of_month,
            end_of_month + timedelta(days=100),
        )
        self.assertEqual(result[1], timezone.make_aware(datetime(2026, 2, 28, 10, 0)))
        self.assertEqual(result[2], timezone.make_aware(datetime(2026, 3, 31, 10, 0)))

    def test_until_stops_series(self):
        result = occurrences(
            {"frequency": "daily", "until": "2026-01-07"},
            START,
            START + timedelta(days=30),
        )
        self.assertEqual(len(result), 3)


class SeriesTests(TestCase):
    def _create(self, **rule):
        return Call.objects.create(
            name="Standup",
            date_start=START,
            date_end=START + timedelta(hours=1),
            recurrence_rule=rule or {"frequency": "daily", "count": 3},
        )

    def test_master_creates_occurrences(self):
        master = self._create()
        self.assertTrue(master.recurrence_uid)
        series = Call.objects.filter(recurrence_uid=master.recurrence_uid)
        self.assertEqual(series.count(), 3)
        self.assertEqual(master.duration, 3600)

        children = series.exclude(pk=master.pk).order_by("date_start")
        self.assertEqual(
            [child.date_start for child in children],
            [START + timedelta(days=1), START + timedelta(days=2)],
        )
        self.assertEqual(children[0].duration, 3600)
        self.assertEqual(children[0].date_end, children[0].date_start + timedelta(hours=1))

    def test_updating_rule_regenerates(self):
        master = self._create()
        master.recurrence_rule = {"frequency": "daily", "count": 2}
        master.save()

        series = Call.objects.filter(recurrence_uid=master.recurrence_uid)
        self.assertEqual(series.count(), 2)

    def test_soft_delete_removes_occurrences(self):
        master = self._create()
        uid = master.recurrence_uid
        master.delete()
        self.assertEqual(Call.objects.filter(recurrence_uid=uid).count(), 0)
        self.assertEqual(Call.all_objects.filter(recurrence_uid=uid).count(), 1)

    def test_master_without_rule_is_unchanged(self):
        event = Call.objects.create(name="One-off", date_start=START)
        self.assertEqual(sync_occurrences(event), 0)

    def test_full_clean_rejects_invalid_rule(self):
        event = Call(name="Bad", date_start=START, recurrence_rule={"frequency": "x"})
        with self.assertRaises(ValidationError):
            event.full_clean()
