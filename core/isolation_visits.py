import hashlib
import json
from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.core import signing
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from packages.access.isolation_visits import verify_booking
from packages.access.calendar_window import calendar_window
from .models import (
    Prospect,
    IsolationVisit,
    IsolationVisitCalendar,
    IsolationVisitResult,
    AuditEvent,
)
from .isolation_work import VisitAuthentication, Pager, Conflict, visible
from .isolation_client import ResultMixin, result_output
from .isolation_sharing import SharingMixin
from .calendar_checks import check as external_check
from .isolation_c2 import captured
from .isolation_closers import CloserAssignmentMixin


class SlotInput(serializers.Serializer):
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    timezone = serializers.CharField(max_length=100)
    proof = serializers.CharField(max_length=3000)
    revision = serializers.IntegerField(min_value=0)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés')
        try:
            zone = ZoneInfo(data['timezone'])
        except (ValueError, ZoneInfoNotFoundError):
            raise ValidationError('Fuseau IANA invalide')
        for key in ('starts_at', 'ends_at'):
            raw = parse_datetime(str(self.initial_data[key]))
            if raw is None or timezone.is_naive(raw):
                raise ValidationError('Date ISO 8601 avec décalage explicite requise')
            if raw.astimezone(zone).utcoffset() != raw.utcoffset():
                raise ValidationError('Décalage incompatible avec le fuseau')
        if not timedelta(0) < data['ends_at'] - data['starts_at'] <= timedelta(days=31):
            raise ValidationError('Fenêtre positive limitée à 31 jours')
        return data


class BookingInput(SlotInput):
    prospect_id = serializers.IntegerField(min_value=1)
    request_id = serializers.UUIDField()


class RescheduleInput(SlotInput):
    reason = serializers.CharField(max_length=1000)


class CancelInput(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(max_length=1000)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés')
        return data


def proof(data, user, prospect):
    try:
        claims = verify_booking(data['proof'], user.pk, prospect.pk)
    except (signing.BadSignature, TypeError, ValueError):
        raise ValidationError('Attestation de réservation invalide ou expirée')
    if prospect.assigned_setter_id is None or claims['setter']['id'] != prospect.assigned_setter_id:
        raise Conflict('Responsable du prospect modifié ou absent')
    return claims


def lock_prospect(prospect, user, revision=None):
    qs = Prospect.objects.filter(pk=prospect.pk)
    if user.role == 'setter':
        qs = qs.filter(assigned_setter_id=user.pk)
    if revision is not None:
        qs = qs.filter(assignment_revision=revision)
    if not qs.update(assignment_revision=F('assignment_revision') + 1):
        raise Conflict('Prospect modifié ou réattribué : rechargez')
    return Prospect.objects.get(pk=prospect.pk)


def calendar(client):
    IsolationVisitCalendar.objects.get_or_create(client_id=client)
    IsolationVisitCalendar.objects.filter(client_id=client).update(version=F('version') + 1)


def available(prospect, client, data, exclude=None):
    if data['starts_at'] <= timezone.now():
        raise ValidationError('Créneau futur requis')
    rows = IsolationVisit.objects.filter(
        status='scheduled', starts_at__lt=data['ends_at'], ends_at__gt=data['starts_at']
    ).filter(Q(client_id=client) | Q(prospect_id=prospect.pk))
    if exclude:
        rows = rows.exclude(pk=exclude)
    if rows.exists():
        raise Conflict('Créneau déjà réservé pour le client ou le prospect')


def output(row):
    try:
        result = result_output(row.result)
    except IsolationVisitResult.DoesNotExist:
        result = None
    return {
        'id': row.pk,
        'prospect': {
            'id': row.prospect_id,
            'name': row.prospect.name,
            'phone': row.prospect.raw_phone,
        },
        'client': {'id': row.client_id, 'name': row.client_name},
        'original_setter': {'id': row.setter_id, 'name': row.setter_name},
        'starts_at': row.starts_at,
        'ends_at': row.ends_at,
        'timezone': row.timezone,
        'status': row.status,
        'revision': row.revision,
        'calendar': 'internal',
        'closer': None if row.closer_id is None else {'id': row.closer_id, 'name': row.closer_name},
        'c2_snapshot': row.c2_snapshot,
        'result': result,
        'result_due': row.status == 'scheduled'
        and row.ends_at <= timezone.now()
        and result is None,
    }


def snapshot(row):
    return {
        key: (
            getattr(row, key).isoformat() if key in ('starts_at', 'ends_at') else getattr(row, key)
        )
        for key in ('starts_at', 'ends_at', 'timezone', 'status', 'revision')
    }


class VisitPager(Pager):
    # The monthly calendar reads a whole team month: larger pages, still bounded.
    page_size_query_param = 'page_size'
    max_page_size = 100


class IsolationVisitViewSet(
    CloserAssignmentMixin, SharingMixin, ResultMixin, viewsets.GenericViewSet
):
    authentication_classes = [VisitAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = BookingInput
    pagination_class = VisitPager
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        qs = IsolationVisit.objects.select_related('prospect', 'result').order_by('starts_at', 'pk')
        if self.request.user.role == 'setter':
            qs = qs.filter(prospect__assigned_setter_id=self.request.user.pk)
        if self.request.user.role == 'client':
            qs = qs.filter(client_id=self.request.user.pk)
        period = self.request.query_params.get('period', '')
        if period not in ('', 'upcoming'):
            raise ValidationError('Période invalide')
        if period == 'upcoming':
            qs = qs.filter(ends_at__gt=timezone.now())
        if self.request.query_params.get('result_due') == 'true':
            qs = qs.filter(status='scheduled', ends_at__lte=timezone.now(), result__isnull=True)
        prospect = self.request.query_params.get('prospect_id', '')
        if prospect:
            if not prospect.isdigit():
                raise ValidationError('Prospect invalide')
            qs = qs.filter(prospect_id=int(prospect))
        # Team calendar filters only narrow the role scope applied above.
        for param in ('setter_id', 'closer_id', 'client_id'):
            value = self.request.query_params.get(param, '')
            if value:
                if not value.isdigit():
                    raise ValidationError('Participant invalide')
                qs = qs.filter(**{param: int(value)})
        state = self.request.query_params.get('status', '')
        if state not in ('', 'scheduled', 'cancelled'):
            raise ValidationError('Statut invalide')
        if state:
            qs = qs.filter(status=state)
        return calendar_window(qs, self.request.query_params)

    def list(self, request):
        return self.get_paginated_response(
            [output(row) for row in self.paginate_queryset(self.get_queryset())]
        )

    def retrieve(self, request, pk=None):
        return Response(output(self.get_object()))

    @action(detail=False, methods=['get'])
    def availability(self, request):
        """Busy CRM intervals before booking; the client's external calendar stays checked at booking."""
        if request.user.role not in ('setter', 'administrator'):
            raise PermissionDenied('Disponibilités réservées aux setters et administrateurs')
        prospect_id = request.query_params.get('prospect_id', '')
        if not prospect_id.isdigit():
            raise ValidationError('Prospect invalide')
        prospect = get_object_or_404(visible(request.user), pk=int(prospect_id))
        start = parse_datetime(request.query_params.get('start', ''))
        end = parse_datetime(request.query_params.get('end', ''))
        if not start or not end or start.tzinfo is None or end.tzinfo is None:
            raise ValidationError('Période invalide : dates ISO 8601 avec décalage attendues')
        if not start < end <= start + timedelta(days=7):
            raise ValidationError('Période invalide : sept jours au maximum')
        # Isolation has a single client (enforced by the portal): every scheduled visit occupies it.
        rows = (
            IsolationVisit.objects.filter(status='scheduled', starts_at__lt=end, ends_at__gt=start)
            .order_by('starts_at', 'pk')
            .values('starts_at', 'ends_at', 'prospect_id')
        )
        # Times only: other prospects' identities are never exposed.
        return Response(
            {
                'busy': [
                    {
                        'starts_at': row['starts_at'],
                        'ends_at': row['ends_at'],
                        'reason': 'prospect' if row['prospect_id'] == prospect.pk else 'client',
                    }
                    for row in rows
                ],
                'external_calendar': 'checked_at_booking',
            }
        )

    def create(self, request):
        if request.user.role == 'client':
            raise PermissionDenied('Réservation réservée aux setters et administrateurs')
        serializer = BookingInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        prospect = get_object_or_404(visible(request.user), pk=data['prospect_id'])
        claims = proof(data, request.user, prospect)
        canonical = {
            key: (data[key].isoformat() if key in ('starts_at', 'ends_at') else data[key])
            for key in ('starts_at', 'ends_at', 'timezone', 'prospect_id')
        }
        canonical.update(client=claims['client']['id'], setter=claims['setter']['id'])
        fingerprint = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()

        def replay(row):
            if row.fingerprint != fingerprint or row.booked_by_id != request.user.pk:
                raise Conflict('Identifiant de réservation déjà utilisé')
            return Response(output(row))

        existing = IsolationVisit.objects.filter(request_id=data['request_id']).first()
        if existing:
            return replay(existing)
        with transaction.atomic():
            try:
                prospect = lock_prospect(prospect, request.user, data['revision'])
            except Conflict:
                existing = IsolationVisit.objects.filter(request_id=data['request_id']).first()
                if existing and visible(request.user).filter(pk=data['prospect_id']).exists():
                    return replay(existing)
                raise
            if prospect.assigned_setter_id != claims['setter']['id']:
                raise Conflict('Responsable modifié : rechargez')
            c2_snapshot = captured(prospect)
            calendar(claims['client']['id'])
            available(prospect, claims['client']['id'], data)
            external = external_check(
                request.user, claims['client']['id'], data['starts_at'], data['ends_at']
            )
            if data['starts_at'] <= timezone.now():
                raise ValidationError('Créneau futur requis')
            row, created = IsolationVisit.objects.get_or_create(
                request_id=data['request_id'],
                defaults={
                    'fingerprint': fingerprint,
                    'prospect': prospect,
                    'c2_snapshot': c2_snapshot,
                    'client_id': claims['client']['id'],
                    'client_name': claims['client']['name'],
                    'setter_id': claims['setter']['id'],
                    'setter_name': claims['setter']['name'],
                    'booked_by_id': request.user.pk,
                    **{key: data[key] for key in ('starts_at', 'ends_at', 'timezone')},
                },
            )
            if not created:
                transaction.set_rollback(True)
                return replay(row)
            from .isolation_followups import event

            event(
                prospect,
                request.user,
                'call_result',
                '',
                {
                    'result': 'appointment_booked',
                    'appointment_id': row.pk,
                    'phone': prospect.raw_phone,
                    'source': 'visit_booking',
                },
            )
            AuditEvent.objects.create(
                action='isolation.visit.booked',
                object_id=str(row.pk),
                metadata={
                    'actor_portal_id': request.user.pk,
                    'prospect_id': prospect.pk,
                    'setter_id': row.setter_id,
                    'client_id': row.client_id,
                    'after': snapshot(row),
                    'external_check': external,
                },
            )
        return Response(output(row), status=201)

    def modify(self, request, cancel=False):
        if request.user.role == 'client':
            raise PermissionDenied('Modification réservée aux setters et administrateurs')
        original = self.get_object()
        serializer = (CancelInput if cancel else RescheduleInput)(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            prospect = lock_prospect(original.prospect, request.user)
            calendar(original.client_id)
            row = IsolationVisit.objects.get(pk=original.pk)
            if (
                row.revision != data['revision']
                or row.status != 'scheduled'
                or row.starts_at <= timezone.now()
                or IsolationVisitResult.objects.filter(visit=row).exists()
            ):
                raise Conflict('Visite modifiée, annulée, renseignée ou déjà commencée')
            before = snapshot(row)
            external = None
            if cancel:
                row.status = 'cancelled'
            else:
                claims = proof(data, request.user, prospect)
                if claims['client']['id'] != row.client_id:
                    raise Conflict('Client de la visite différent de la configuration active')
                available(prospect, row.client_id, data, exclude=row.pk)
                external = external_check(
                    request.user, row.client_id, data['starts_at'], data['ends_at'], row.pk
                )
                if data['starts_at'] <= timezone.now():
                    raise ValidationError('Créneau futur requis')
                for key in ('starts_at', 'ends_at', 'timezone'):
                    setattr(row, key, data[key])
            row.revision += 1
            row.save(update_fields=['starts_at', 'ends_at', 'timezone', 'status', 'revision'])
            AuditEvent.objects.create(
                action='isolation.visit.cancelled' if cancel else 'isolation.visit.rescheduled',
                object_id=str(row.pk),
                metadata={
                    'actor_portal_id': request.user.pk,
                    'before': before,
                    'after': snapshot(row),
                    'reason': data['reason'],
                    **({'external_check': external} if external else {}),
                },
            )
        return Response(output(row))

    @action(detail=True, methods=['post'])
    def reschedule(self, request, pk=None):
        return self.modify(request)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        return self.modify(request, cancel=True)

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        if request.user.role != 'administrator':
            raise PermissionDenied('Historique administratif uniquement')
        row = self.get_object()
        qs = AuditEvent.objects.filter(
            object_id=str(row.pk), action__startswith='isolation.visit.'
        ).order_by('-pk')
        return self.get_paginated_response(
            [
                {
                    'id': entry.pk,
                    'action': entry.action,
                    'created_at': entry.created_at,
                    'metadata': entry.metadata,
                }
                for entry in self.paginate_queryset(qs)
            ]
        )
