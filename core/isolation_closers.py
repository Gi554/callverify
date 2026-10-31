"""Assigned closer workspace and versioned visit results; no call commands."""

import hashlib
import json
from django.core import signing
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from packages.access.isolation_visits import verify_closer
from .isolation_work import WorkAuthentication, Pager, Conflict
from .models import IsolationVisit, IsolationVisitResult, AuditEvent, Prospect


class AssignmentInput(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0)
    proof = serializers.CharField(max_length=3000)
    reason = serializers.CharField(max_length=1000)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés.')
        return data


class CloserAssignmentMixin:
    @action(detail=True, methods=['post'], url_path='assign-closer')
    def assign_closer(self, request, pk=None):
        if request.user.role not in ('administrator', 'client'):
            raise PermissionDenied('Attribution réservée au client et à l’administration.')
        original = self.get_object()
        serializer = AssignmentInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            claims = verify_closer(data['proof'], request.user.pk, original.pk)
        except (signing.BadSignature, TypeError, ValueError):
            raise ValidationError('Attestation de closer invalide ou expirée.')
        with transaction.atomic():
            rows = IsolationVisit.objects.filter(
                pk=original.pk, revision=data['revision'], status='scheduled'
            )
            if request.user.role == 'client':
                rows = rows.filter(client_id=request.user.pk)
            if not rows.update(
                revision=F('revision') + 1, closer_id=claims['closer'], closer_name=claims['name']
            ):
                raise Conflict('Visite modifiée ou annulée : actualisez avant l’attribution.')
            AuditEvent.objects.create(
                action='isolation.visit.closer_assigned',
                object_id=str(original.pk),
                metadata={
                    'actor_portal_id': request.user.pk,
                    'before': {'id': original.closer_id, 'name': original.closer_name},
                    'after': {'id': claims['closer'], 'name': claims['name']},
                    'reason': data['reason'],
                    'revision': data['revision'] + 1,
                },
            )
        from .isolation_visits import output

        return Response(
            output(IsolationVisit.objects.select_related('prospect', 'result').get(pk=original.pk))
        )


class CloserAuthentication(WorkAuthentication):
    roles = ('closer',)


class ClosingInput(serializers.Serializer):
    request_id = serializers.UUIDField()
    revision = serializers.IntegerField(min_value=0)
    performed = serializers.BooleanField()
    closed = serializers.BooleanField()
    note = serializers.CharField(max_length=3000, allow_blank=True, default='')
    reason = serializers.CharField(max_length=1000, allow_blank=True, default='')

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés.')
        if data['closed'] and not data['performed']:
            raise ValidationError('Une vente conclue exige un rendez-vous tenu.')
        return data


def state(row):
    return (
        None
        if row is None
        else {
            'performed': row.performed,
            'closed': row.closed,
            'outcome': row.outcome,
            'note': row.note,
            'author_client_id': row.author_client_id,
            'author_closer_id': row.author_closer_id,
        }
    )


class CloserVisits(viewsets.GenericViewSet):
    authentication_classes = [CloserAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = Pager
    serializer_class = ClosingInput
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        rows = (
            IsolationVisit.objects.filter(closer_id=self.request.user.pk)
            .select_related('prospect', 'result')
            .order_by('starts_at', 'pk')
        )
        period = self.request.query_params.get('period', '')
        if period not in ('', 'upcoming'):
            raise ValidationError('Période invalide.')
        if period == 'upcoming':
            rows = rows.filter(ends_at__gt=timezone.now(), status='scheduled')
        if self.request.query_params.get('result_due') == 'true':
            rows = rows.filter(status='scheduled', ends_at__lte=timezone.now()).filter(
                Q(result__isnull=True) | Q(result__closed__isnull=True)
            )
        return rows

    def list(self, request):
        from .isolation_visits import output

        response = self.get_paginated_response(
            [output(row) for row in self.paginate_queryset(self.get_queryset())]
        )
        response['Cache-Control'] = 'no-store'
        return response

    def retrieve(self, request, pk=None):
        from .isolation_visits import output

        response = Response(output(self.get_object()))
        response['Cache-Control'] = 'no-store'
        return response

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        rows = self.get_queryset()
        now = timezone.now()
        return Response(
            {
                'role': 'closer',
                'prospects': rows.values('prospect_id').distinct().count(),
                'visits': rows.count(),
                'upcoming': rows.filter(status='scheduled', starts_at__gt=now).count(),
                'results_due': rows.filter(status='scheduled', ends_at__lte=now)
                .filter(Q(result__isnull=True) | Q(result__closed__isnull=True))
                .count(),
            }
        )

    @action(detail=True, methods=['get', 'post'])
    def result(self, request, pk=None):
        from .isolation_client import result_output

        original = self.get_object()
        if request.method == 'GET':
            row = IsolationVisitResult.objects.filter(visit=original).first()
            return Response(None if row is None else result_output(row))
        serializer = ClosingInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        fingerprint = hashlib.sha256(
            json.dumps(data, sort_keys=True, default=str).encode()
        ).hexdigest()
        with transaction.atomic():
            Prospect.objects.filter(pk=original.prospect_id).update(
                assignment_revision=F('assignment_revision')
            )
            if not IsolationVisit.objects.filter(pk=original.pk, closer_id=request.user.pk).update(
                revision=F('revision')
            ):
                raise Conflict('Visite réattribuée : accès retiré.')
            row = IsolationVisit.objects.get(pk=original.pk)
            previous = AuditEvent.objects.filter(
                action='isolation.visit.closer_reported',
                object_id=str(row.pk),
                metadata__request_id=str(data['request_id']),
            ).first()
            if previous:
                if (
                    previous.metadata['fingerprint'] != fingerprint
                    or previous.metadata['actor_portal_id'] != request.user.pk
                ):
                    raise Conflict('Identifiant de compte rendu déjà utilisé.')
                return Response({'recorded': True, 'revision': previous.metadata['revision']})
            if row.status != 'scheduled' or row.ends_at > timezone.now():
                raise Conflict('Résultat attendu après la fin d’une visite non annulée.')
            if row.revision != data['revision']:
                raise Conflict('Visite modifiée : actualisez avant de répondre.')
            report = IsolationVisitResult.objects.filter(visit=row).first()
            before = state(report)
            if report and not data['reason'].strip():
                raise ValidationError('Motif obligatoire pour corriger un résultat existant.')
            report, _ = IsolationVisitResult.objects.update_or_create(
                visit=row,
                defaults={
                    'performed': data['performed'],
                    'closed': data['closed'],
                    'note': data['note'],
                    'outcome': 'closed'
                    if data['closed']
                    else 'completed'
                    if data['performed']
                    else 'not_performed',
                    'author_client_id': None,
                    'author_closer_id': request.user.pk,
                },
            )
            row.revision += 1
            row.save(update_fields=['revision'])
            from .isolation_notices import result_changed

            result_changed(row, report, before, request.user)
            AuditEvent.objects.create(
                action='isolation.visit.closer_reported',
                object_id=str(row.pk),
                metadata={
                    'request_id': str(data['request_id']),
                    'fingerprint': fingerprint,
                    'actor_portal_id': request.user.pk,
                    'before': before,
                    'after': state(report),
                    'reason': data['reason'],
                    'revision': row.revision,
                },
            )
        return Response({'recorded': True, 'revision': row.revision}, status=200 if before else 201)

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        row = self.get_object()
        entries = AuditEvent.objects.filter(
            object_id=str(row.pk), action='isolation.visit.closer_reported'
        ).order_by('-pk')
        return self.get_paginated_response(
            [
                {
                    'id': entry.pk,
                    'created_at': entry.created_at,
                    'before': entry.metadata['before'],
                    'after': entry.metadata['after'],
                    'reason': entry.metadata['reason'],
                    'actor_id': entry.metadata['actor_portal_id'],
                }
                for entry in self.paginate_queryset(entries)
            ]
        )
