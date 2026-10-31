"""Publish one committed Isolation intent; status callback is outside provider locks."""

from urllib.parse import urlsplit
import requests
from django.conf import settings
from django.core import signing
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from packages.access.isolation_events import issue, verify
from .models import CalendarConnection, CalendarSync
from .booking_calendars import active
from .calendars import Unavailable


def feedback(connection, pk):
    ledger = CalendarSync.objects.filter(
        connection=connection, source_id=pk, isolation_publication=True
    ).first()
    if ledger is None or ledger.source_revision < 0 or ledger.checked_at is None:
        return True
    state = {
        'synced': 'confirmed',
        'removed': 'removed',
        'error': 'error',
        'pending': 'pending',
    }.get(ledger.status)
    if state is None:
        return True
    base = settings.ISOLATION_INTERNAL_URL.rstrip('/')
    parsed = urlsplit(base)
    if (
        parsed.scheme not in ('http', 'https')
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        return False
    proof = issue(
        'publication_status',
        visit=pk,
        owner=connection.user_id,
        revision=ledger.source_revision,
        state=state,
        checked_at=ledger.checked_at.isoformat(),
        error=ledger.error_code,
    )
    try:
        response = requests.post(
            base + '/api/internal/isolation/publication-status/',
            json={'proof': proof},
            headers={'X-Forwarded-Proto': 'https'},
            timeout=10,
            allow_redirects=False,
        )
        return response.status_code == 200
    except requests.RequestException:
        return False


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def publish(request):
    try:
        if (
            not isinstance(request.data, dict)
            or set(request.data) != {'proof'}
            or not isinstance(request.data['proof'], str)
            or len(request.data['proof']) > 8192
        ):
            raise signing.BadSignature()
        data = verify(request.data['proof'], 'publish_visit')
        if (
            set(data) != {'actor', 'role', 'owner', 'visit'}
            or data['role'] not in ('administrator', 'setter', 'client')
            or any(type(data[k]) is not int or data[k] < 1 for k in ('actor', 'owner', 'visit'))
        ):
            raise signing.BadSignature()
    except (signing.BadSignature, TypeError, ValueError):
        raise PermissionDenied('Publication serveur Isolation requise.') from None
    if not active(data['actor'], data['role'], 'isolation') or not active(
        data['owner'], 'client', 'isolation'
    ):
        raise PermissionDenied('Participants actifs requis.')
    connection = (
        CalendarConnection.objects.filter(
            user_id=data['owner'],
            workspace='isolation',
            provider='google',
            connected=True,
            auto_sync=True,
        )
        .select_related('user')
        .first()
    )
    if connection is None:
        raise Unavailable()
    from .calendar_sync import sync_one

    state = sync_one(connection, data['visit'])
    return Response({'state': state})
