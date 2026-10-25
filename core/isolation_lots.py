"""Weekly lots: an administrator hands a number of unassigned prospects to one setter."""

import hashlib
import json
from datetime import timedelta
from django.core import signing
from django.db import transaction
from django.db.models import Case, CharField, Count, Exists, F, OuterRef, Max, Value, When
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from packages.access.isolation import verify_lot
from .models import AuditEvent, IsolationAssignmentBatch, IsolationVisit, Prospect

MAX_LOT = 1000


class AssignInput(serializers.Serializer):
    request_id = serializers.UUIDField()
    proof = serializers.CharField(max_length=3000)
    count = serializers.IntegerField(min_value=1, max_value=MAX_LOT)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés')
        return data


class ReleaseInput(serializers.Serializer):
    request_id = serializers.UUIDField()
    setter_id = serializers.IntegerField(min_value=1)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés')
        return data


def admin(user):
    if user.role != 'administrator':
        raise PermissionDenied('Lots réservés aux administrateurs Isolation')


def week_start(day):
    return day - timedelta(days=day.weekday())


def active(qs):
    """Prospects still to work: not booked and not declined."""
    booked = IsolationVisit.objects.filter(prospect_id=OuterRef('pk'), status='scheduled')
    return (
        qs.annotate(_lot_booked=Exists(booked))
        .annotate(
            _lot_reason=Case(
                When(_lot_booked=True, then=Value('appointment_booked')),
                When(commercial_status='not_interested', then=Value('not_interested')),
                default=Value(''),
                output_field=CharField(),
            )
        )
        .filter(_lot_reason='')
    )


def fingerprint(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


class LotMixin:
    @action(detail=False, methods=['get'], url_path='lots')
    def lots(self, request):
        admin(request.user)
        free = active(Prospect.objects.filter(assigned_setter_id__isnull=True))
        rows = (
            active(Prospect.objects.filter(assigned_setter_id__isnull=False))
            .values('assigned_setter_id', 'assigned_setter_name')
            .annotate(n=Count('pk'), week=Max('lot_week'))
            .order_by('assigned_setter_name')
        )
        response = Response(
            {
                'available': free.count(),
                'week': week_start(timezone.localdate()),
                'setters': [
                    {
                        'id': row['assigned_setter_id'],
                        'name': row['assigned_setter_name'],
                        'assigned': row['n'],
                        'week': row['week'],
                    }
                    for row in rows
                ],
            }
        )
        response['Cache-Control'] = 'no-store'
        return response

    @action(detail=False, methods=['post'], url_path='lots/assign')
    def lot_assign(self, request):
        from .isolation_work import Conflict

        admin(request.user)
        serializer = AssignInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            claims = verify_lot(data['proof'], request.user.pk)
        except (signing.BadSignature, ValueError, TypeError):
            raise ValidationError('Attestation invalide ou expirée : recommencez')
        canonical = fingerprint({'kind': 'lot', 'setter': claims['setter'], 'count': data['count']})

        def replay(batch):
            if (batch.actor_portal_id, batch.fingerprint) != (request.user.pk, canonical):
                raise Conflict('Identifiant de lot déjà utilisé')
            return Response({**batch.result, 'replayed': True})

        existing = IsolationAssignmentBatch.objects.filter(request_id=data['request_id']).first()
        if existing:
            return replay(existing)
        with transaction.atomic():
            batch, created = IsolationAssignmentBatch.objects.get_or_create(
                request_id=data['request_id'],
                defaults={'actor_portal_id': request.user.pk, 'fingerprint': canonical},
            )
            if not created:
                return replay(batch)
            ids = list(
                active(Prospect.objects.filter(assigned_setter_id__isnull=True))
                .order_by('pk')
                .values_list('pk', flat=True)[: data['count']]
            )
            now = timezone.now()
            count = Prospect.objects.filter(pk__in=ids, assigned_setter_id__isnull=True).update(
                assigned_setter_id=claims['setter'],
                assigned_setter_name=claims['name'],
                assignment_revision=F('assignment_revision') + 1,
                lot_week=week_start(timezone.localdate()),
                assigned_at=now,
            )
            AuditEvent.objects.create(
                action='isolation.lot.assigned',
                object_id=str(claims['setter']),
                metadata={
                    'actor_portal_id': request.user.pk,
                    'batch': str(batch.request_id),
                    'count': count,
                    'setter_name': claims['name'],
                },
            )
            batch.result = {'request_id': str(batch.request_id), 'assigned': count}
            batch.save(update_fields=['result'])
        return Response(batch.result, status=201)

    @action(detail=False, methods=['post'], url_path='lots/release')
    def lot_release(self, request):
        from .isolation_work import Conflict

        admin(request.user)
        serializer = ReleaseInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        canonical = fingerprint({'kind': 'release', 'setter': data['setter_id']})

        def replay(batch):
            if (batch.actor_portal_id, batch.fingerprint) != (request.user.pk, canonical):
                raise Conflict('Identifiant de lot déjà utilisé')
            return Response({**batch.result, 'replayed': True})

        existing = IsolationAssignmentBatch.objects.filter(request_id=data['request_id']).first()
        if existing:
            return replay(existing)
        with transaction.atomic():
            batch, created = IsolationAssignmentBatch.objects.get_or_create(
                request_id=data['request_id'],
                defaults={'actor_portal_id': request.user.pk, 'fingerprint': canonical},
            )
            if not created:
                return replay(batch)
            # Only prospects nobody has worked yet go back to the pool.
            ids = list(
                active(Prospect.objects.filter(assigned_setter_id=data['setter_id']))
                .filter(commercial_status='to_contact')
                .values_list('pk', flat=True)
            )
            count = Prospect.objects.filter(pk__in=ids).update(
                assigned_setter_id=None,
                assigned_setter_name='',
                assignment_revision=F('assignment_revision') + 1,
                lot_week=None,
                assigned_at=None,
            )
            AuditEvent.objects.create(
                action='isolation.lot.released',
                object_id=str(data['setter_id']),
                metadata={
                    'actor_portal_id': request.user.pk,
                    'batch': str(batch.request_id),
                    'count': count,
                },
            )
            batch.result = {'request_id': str(batch.request_id), 'released': count}
            batch.save(update_fields=['result'])
        return Response(batch.result)
