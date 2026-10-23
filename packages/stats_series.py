"""Daily series and previous-period window shared by the statistics dashboards."""

from datetime import timedelta
from django.db.models.functions import TruncDate


def previous(start, end):
    """The period of the same length just before [start, end]."""
    length = (end - start).days + 1
    return start - timedelta(days=length), start - timedelta(days=1)


def daily(queryset, start, end, tzinfo, **counts):
    """One row per day of [start, end], zero-filled, keyed on the local start date."""
    rows = (
        queryset.order_by()
        .annotate(day=TruncDate('starts_at', tzinfo=tzinfo))
        .values('day')
        .annotate(**counts)
    )
    found = {row['day']: row for row in rows}
    series, day = [], start
    while day <= end:
        row = found.get(day, {})
        series.append({'day': day, **{key: row.get(key, 0) for key in counts}})
        day += timedelta(days=1)
    return series
