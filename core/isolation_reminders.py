"""One gentle client reminder per scheduled occurrence; never infer non-attendance."""

import hashlib
from datetime import timedelta
from django.core import signing
from django.db import transaction
from django.db.models import Q, F
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from packages.access.isolation_events import verify
from .models import IsolationVisit, IsolationNotice, IsolationReminderPolicy, AuditEvent
from .isolation_work import VisitAuthentication, Conflict
from .isolation_notices import notice


def policy():
    row, _ = IsolationReminderPolicy.objects.get_or_create(pk=1)
    return row


def output(row):
    return {'enabled': row.enabled, 'delay_hours': row.delay_hours, 'revision': row.revision}


def eligible_due(rules, now):
    return Q(
        visit__ends_at__lte=now - timedelta(hours=rules.delay_hours),
        visit__ends_at__gte=rules.active_from,
    ) & (Q(visit__result__isnull=True) | Q(visit__result__closed__isnull=True))


def candidates():
    rules = policy()
    now = timezone.now()
    available = Q(
        kind='booked',
        visit__starts_at__gt=now,
        visit__publication='google',
        visit__publication_status='confirmed',
        visit__created_at__gte=rules.active_from,
    )
    if rules.enabled:
        available |= (
            Q(kind='result_due')
            & eligible_due(rules, now)
            & (
                Q(visit__publication='internal')
                | Q(visit__publication='google', visit__publication_status='confirmed')
            )
        )
    return IsolationNotice.objects.filter(
        available,
        recipient_role='client',
        recipient_id=F('visit__client_id'),
        anchor_at=F('visit__starts_at'),
        visit__status='scheduled',
        created_at__gte=now - timedelta(days=7),
    )


def booked(visit):
    if (
        visit.status != 'scheduled'
        or visit.publication != 'google'
        or visit.publication_status != 'confirmed'
        or visit.created_at < policy().active_from
    ):
        return
    key = hashlib.sha256(
        f'booked:{visit.pk}:{visit.client_id}:{visit.starts_at.isoformat()}'.encode()
    ).hexdigest()
    notice(visit, visit.client_id, 'client', 'booked', key)


def generate():
    rules = policy()
    now = timezone.now()
    for visit in IsolationVisit.objects.filter(
        status='scheduled',
        publication='google',
        publication_status='confirmed',
        starts_at__gt=now,
        created_at__gte=rules.active_from,
    ).iterator(chunk_size=200):
        booked(visit)
    if not rules.enabled:
        return {'created': 0}
    rows = (
        IsolationVisit.objects.filter(
            status='scheduled',
            ends_at__gte=rules.active_from,
            ends_at__lte=now - timedelta(hours=rules.delay_hours),
            ends_at__gt=now - timedelta(hours=rules.delay_hours, days=7),
        )
        .filter(Q(result__isnull=True) | Q(result__closed__isnull=True))
        .filter(Q(publication='internal') | Q(publication='google', publication_status='confirmed'))
    )
    count = 0
    for visit in rows.iterator(chunk_size=200):
        key = hashlib.sha256(
            f'due:{visit.pk}:{visit.client_id}:{visit.starts_at.isoformat()}'.encode()
        ).hexdigest()
        _, created = IsolationNotice.objects.get_or_create(
            event_key=key,
            defaults={
                'visit': visit,
                'recipient_id': visit.client_id,
                'recipient_role': 'client',
                'kind': 'result_due',
                'anchor_at': visit.starts_at,
            },
        )
        count += created
    return {'created': count}


class Input(serializers.Serializer):
    enabled = serializers.BooleanField()
    delay_hours = serializers.IntegerField(min_value=1, max_value=720)
    revision = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(max_length=1000)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés.')
        return data


@api_view(['GET', 'POST'])
@authentication_classes([VisitAuthentication])
@permission_classes([IsAuthenticated])
def configuration(request):
    if request.user.role != 'administrator':
        raise PermissionDenied('Règle de relance réservée à l’administration Isolation.')
    if request.method == 'GET':
        return Response(output(policy()))
    serializer = Input(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    with transaction.atomic():
        row = policy()
        before = output(row)
        if not IsolationReminderPolicy.objects.filter(pk=1, revision=data['revision']).update(
            enabled=data['enabled'], delay_hours=data['delay_hours'], revision=F('revision') + 1
        ):
            raise Conflict('Règle modifiée : rechargez.')
        row.refresh_from_db()
        AuditEvent.objects.create(
            action='isolation.reminder_policy.updated',
            object_id='1',
            metadata={
                'actor_portal_id': request.user.pk,
                'reason': data['reason'],
                'before': before,
                'after': output(row),
            },
        )
    return Response(output(row))


def authorize(request, operation, claims):
    token = request.headers.get('Authorization', '')
    try:
        if not token.startswith('Bearer ') or verify(token[7:], operation) != claims:
            raise signing.BadSignature()
    except (signing.BadSignature, TypeError, ValueError):
        raise PermissionDenied('Échange serveur Isolation requis.') from None


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def mail_events(request):
    try:
        after = int(request.query_params.get('after', '0'))
        if not 0 <= after <= 9223372036854775807:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValidationError('Curseur invalide.') from None
    authorize(request, 'mail_events', {'after': after})
    rows = candidates().filter(pk__gt=after).select_related('visit__prospect').order_by('pk')[:100]
    response = Response(
        {
            'events': [
                {
                    'id': r.pk,
                    'recipient_id': r.recipient_id,
                    'visit_id': r.visit_id,
                    'kind': r.kind,
                    'created_at': r.created_at,
                    'prospect_name': r.visit.prospect.name or 'Prospect',
                    'starts_at': r.visit.starts_at,
                }
                for r in rows
            ]
        }
    )
    response['Cache-Control'] = 'no-store'
    return response


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def mail_eligible(request, pk, user_id):
    authorize(request, 'mail_eligible', {'event': pk, 'user': user_id})
    response = Response({'eligible': candidates().filter(pk=pk, recipient_id=user_id).exists()})
    response['Cache-Control'] = 'no-store'
    return response
