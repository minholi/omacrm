"""Shared helpers for the demo-data seeders."""

import random
from datetime import datetime, time, timedelta

from django.core.files.base import ContentFile
from django.utils import timezone

DEFAULT_SEED = 42


def make_rng(seed=None) -> random.Random:
    return random.Random(DEFAULT_SEED if seed is None else seed)


def today():
    return timezone.localdate()


def date_in(days: int):
    return timezone.localdate() + timedelta(days=days)


def moment_in(days: int, hour: int = 10, minute: int = 0):
    day = timezone.localdate() + timedelta(days=days)
    naive = datetime.combine(day, time(hour, minute))
    if timezone.is_naive(naive):
        naive = timezone.make_aware(naive)
    return naive


def text_file(filename: str, content: str) -> ContentFile:
    return ContentFile(content.encode("utf-8"), name=filename)
