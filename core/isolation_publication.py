"""Durable Google publication intents and authenticated status feedback."""

from datetime import timedelta
from django.core import signing
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from packages.access.isolation_events import verify
from .models import IsolationVisit, AuditEvent

ERRORS = {
    'provider_unavailable',
    'slot_busy',
    'event_changed',
    'event_has_attendees',
    'uncertain_create',
    'source_unavailable',
    'source_changed',
    'past_source',
}


class Status(serializers.Serializer):
    visit = serializers.IntegerField(min_value=1)
    owner = serializers.IntegerField(min_value=1)
    revision = serializers.IntegerField(min_value=0)
    state = serializers.ChoiceField(choices=['confirmed', 'error', 'pending', 'removed'])
    checked_at = serializers.DateTimeField()
    error = serializers.ChoiceField(choices=['', *sorted(ERRORS)])


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def status(request):
    try:
        if (
            not isinstance(request.data, dict)
            or set(request.data) != {'proof'}
            or not isinstance(request.data['proof'], str)
            or len(request.data['proof']) > 8192
        ):
            raise signing.BadSignature()
        data = verify(request.data['proof'], 'publication_status')
    except (signing.BadSignature, TypeError, ValueError):
        raise PermissionDenied('Échange serveur Isolation requis.') from None
    if set(data) != set(Status().fields):
        raise PermissionDenied('Échange serveur invalide.')
    serializer = Status(data=data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if abs(timezone.now() - data['checked_at']) > timedelta(minutes=5):
        raise PermissionDenied('État de publication expiré.')
    with transaction.atomic():
        row = (
            IsolationVisit.objects.select_for_update()
            .filter(pk=data['visit'], client_id=data['owner'], publication='google')
            .first()
        )
        if row is None or row.revision != data['revision']:
            return Response({'applied': False})
        if row.publication_checked_at and row.publication_checked_at >= data['checked_at']:
            return Response({'applied': False})
        if row.status == 'cancelled' and data['state'] == 'confirmed':
            return Response({'applied': False})
        changed = (row.publication_status, row.publication_error) != (data['state'], data['error'])
        row.publication_status = data['state']
        row.publication_error = data['error']
        row.publication_checked_at = data['checked_at']
        row.save(
            update_fields=['publication_status', 'publication_error', 'publication_checked_at']
        )
        if changed:
            AuditEvent.objects.create(
                action='isolation.visit.publication_checked',
                object_id=str(row.pk),
                metadata={'state': data['state'], 'error': data['error'], 'revision': row.revision},
            )
    return Response({'applied': True})
