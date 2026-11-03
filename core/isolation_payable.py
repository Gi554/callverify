from rest_framework.decorators import api_view
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q
from packages.payable_appointments import payable
from packages.quebec_period import period
from . import models
from .isolation_alerts import Store as AlertStore
from .isolation_work import WorkAuthentication


class Store(AlertStore):
    # Isolation pays attended appointments, counted apart when the sale was concluded.
    split_sales = True
    Entry = models.PayableEntry
    History = models.PayableHistory
    parent = 'visit'


@api_view(['GET'])
@authentication_classes([WorkAuthentication])
@permission_classes([IsAuthenticated])
def appointments(request):
    return payable(Store, request)


def setter_payable(setter_id, params=None):
    """A setter's payable appointments of a period, from the ledger of confirmed attendances."""
    start, end, lower, upper = period(params or {})
    rows = models.PayableEntry.objects.filter(
        setter_id=setter_id,
        counted_at__gte=lower,
        counted_at__lt=upper,
        withdrawn_at__isnull=True,
    )
    return {
        'from': start.isoformat(),
        'to': end.isoformat(),
        'timezone': 'America/Toronto',
        **rows.aggregate(
            payable=Count('pk'),
            presented_closed=Count('pk', filter=Q(closed_at_count=True)),
            presented_not_closed=Count('pk', filter=Q(closed_at_count=False)),
        ),
        'sale_unknown': 0,
    }
