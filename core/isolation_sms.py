"""Signed feed of future Isolation visits for prospect SMS notifications."""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .isolation_reminders import authorize
from .models import IsolationVisit


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def visits(request):
    raw_since = request.query_params.get('since', '')
    try:
        since = parse_datetime(raw_since)
        after = int(request.query_params.get('after', '0'))
        visit = int(request.query_params.get('visit', '0'))
        if (
            since is None
            or timezone.is_naive(since)
            or not all(0 <= value <= 9223372036854775807 for value in (after, visit))
        ):
            raise ValueError()
    except (ValueError, OverflowError):
        raise ValidationError('Paramètres SMS invalides.') from None
    authorize(request, 'sms_visits', {'since': raw_since, 'after': after, 'visit': visit})
    now = timezone.now()
    rows = IsolationVisit.objects.filter(
        pk__gt=after,
        status='scheduled',
        starts_at__gt=now,
        created_at__gte=since,
    ).filter(Q(publication='internal') | Q(publication='google', publication_status='confirmed'))
    rows = rows.filter(
        Q(created_at__gte=now - timedelta(days=7)) | Q(starts_at__lte=now + timedelta(hours=24))
    )
    if visit:
        rows = rows.filter(pk=visit)
    response = Response(
        {
            'visits': [
                {
                    'id': row.pk,
                    'starts_at': row.starts_at,
                    'created_at': row.created_at,
                    'phone': row.c2_snapshot.get('fields', {}).get('phone', ''),
                }
                for row in rows.order_by('pk')[:100]
            ]
        }
    )
    response['Cache-Control'] = 'no-store'
    return response
