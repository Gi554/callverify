"""Signed aggregate bridge. No telephone numbers, extensions or contact identities."""

from django.core import signing
from django.db.models import Count, Q
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from packages.access.isolation_events import verify
from packages.quebec_period import period
from .models import PhoneCallAttempt, Membership


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def statistics(request):
    try:
        header = request.headers.get('Authorization', '')
        data = verify(header[7:] if header.startswith('Bearer ') else '', 'compensation_calls')
        if (
            set(data) != {'actor', 'from', 'to'}
            or type(data['actor']) is not int
            or data['actor'] <= 0
        ):
            raise signing.BadSignature()
        if set(request.query_params) != {'from', 'to'} or any(
            data[key] != request.query_params[key] for key in ('from', 'to')
        ):
            raise signing.BadSignature()
    except (signing.BadSignature, TypeError, ValueError, KeyError):
        raise PermissionDenied('Preuve serveur requise.') from None
    if not Membership.objects.filter(
        user_id=data['actor'],
        workspace='isolation',
        role='administrator',
        active=True,
        user__is_active=True,
    ).exists():
        raise PermissionDenied('Administrateur Isolation actif requis.')
    start, end, lower, upper = period(request.query_params)
    metrics = {
        'calls': Count('pk', filter=Q(state='accepted')),
        'attempts': Count('pk', filter=Q(state__in=['accepted', 'rejected', 'unknown'])),
        'uncertain': Count('pk', filter=Q(state='unknown')),
    }
    rows = PhoneCallAttempt.objects.filter(
        workspace='isolation', created_at__gte=lower, created_at__lt=upper
    )
    groups = rows.values('user_id', 'user__username').annotate(**metrics).order_by('user_id')
    if groups.count() > 5000:
        raise ValidationError('Trop de groupes pour cette période.')
    client = (
        Membership.objects.filter(
            workspace='isolation', role='client', active=True, user__is_active=True
        )
        .select_related('user')
        .first()
    )
    response = Response(
        {
            'from': start,
            'to': end,
            'client': None
            if client is None
            else {'id': client.user_id, 'name': client.user.username},
            'results': list(groups),
            'totals': rows.aggregate(**metrics),
        }
    )
    response['Cache-Control'] = 'no-store'
    return response
