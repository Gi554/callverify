"""Shared local-day boundaries for Assurance business and portal call counters."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError

ZONE = ZoneInfo('America/Toronto')


def period(params):
    today = timezone.now().astimezone(ZONE).date()
    monday = today - timedelta(days=today.weekday())
    try:
        start = parse_date(params.get('from', monday.isoformat()))
        end = parse_date(params.get('to', (monday + timedelta(days=6)).isoformat()))
        if start is None or end is None or not 0 <= (end - start).days <= 365:
            raise ValueError()
        upper = end + timedelta(days=1)
    except (ValueError, TypeError, OverflowError):
        raise ValidationError(
            'Période valide de 366 jours maximum, au format AAAA-MM-JJ.'
        ) from None
    return (
        start,
        end,
        datetime.combine(start, time.min, ZONE),
        datetime.combine(upper, time.min, ZONE),
    )
