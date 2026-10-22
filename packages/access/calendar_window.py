"""Optional, bounded calendar viewport; preserves the caller's visibility queryset."""

from datetime import timedelta
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError


def calendar_window(queryset, params):
    before, after = params.get('starts_before'), params.get('ends_after')
    if before is None and after is None:
        return queryset
    try:
        start, end = parse_datetime(after or ''), parse_datetime(before or '')
        if start is None or end is None or timezone.is_naive(start) or timezone.is_naive(end):
            raise ValueError()
        if not timedelta(0) < end - start <= timedelta(days=62):
            raise ValueError()
    except (ValueError, TypeError, OverflowError):
        raise ValidationError(
            'Fenêtre calendrier de 62 jours maximum, avec deux dates ISO 8601 et décalages explicites, requise.'
        )
    return queryset.filter(starts_at__lt=end, ends_at__gt=start)
