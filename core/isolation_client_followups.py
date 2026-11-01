"""Client-owned callbacks. They never appear in a setter's callback queue."""

import hashlib
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .isolation_work import VisitAuthentication, Pager, Conflict
from .isolation_followups import explicit, event
from .models import IsolationClientFollowUp, IsolationNotice, Prospect


def output(row):
    visit = row.visit
    fields = visit.c2_snapshot.get('fields', {})
    return {
        'id': row.pk,
        'visit_id': visit.pk,
        'prospect_id': visit.prospect_id,
        'name': fields.get('full_name') or visit.prospect.name,
        'phone': fields.get('phone') or visit.prospect.raw_phone,
        'client': {'id': visit.client_id, 'name': visit.client_name},
        'setter': {'id': visit.setter_id, 'name': visit.setter_name},
        'reason': row.reason,
        'note': row.note,
        'due_at': row.due_at,
        'revision': row.revision,
        'closed_at': row.closed_at,
        'programmed_visit_id': row.programmed_visit_id,
    }


class Update(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0)
    note = serializers.CharField(max_length=3000, allow_blank=True)
    due_at = serializers.DateTimeField(allow_null=True)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés.')
        if data['due_at']:
            explicit(data['due_at'], self.initial_data['due_at'])
        return data


class ClientFollowUps(viewsets.GenericViewSet):
    authentication_classes = [VisitAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = Pager

    def get_queryset(self):
        if self.request.user.role not in ('client', 'administrator'):
            raise PermissionDenied('Relances personnelles du client uniquement.')
        rows = IsolationClientFollowUp.objects.select_related('visit__prospect', 'visit__result')
        if self.request.user.role == 'client':
            rows = rows.filter(visit__client_id=self.request.user.pk)
        return rows.order_by(F('due_at').asc(nulls_last=True), 'pk')

    def list(self, request):
        rows = self.paginate_queryset(self.get_queryset().filter(closed_at__isnull=True))
        response = self.get_paginated_response([output(row) for row in rows])
        response['Cache-Control'] = 'no-store'
        return response

    def retrieve(self, request, pk=None):
        response = Response(output(self.get_object()))
        response['Cache-Control'] = 'no-store'
        return response

    @action(detail=True, methods=['post'])
    def update_plan(self, request, pk=None):
        if request.user.role != 'client':
            raise PermissionDenied('Seul le client peut modifier sa relance personnelle.')
        original = self.get_object()
        serializer = Update(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            Prospect.objects.filter(pk=original.visit.prospect_id).update(
                assignment_revision=F('assignment_revision')
            )
            if not IsolationClientFollowUp.objects.filter(
                pk=original.pk,
                revision=data['revision'],
                closed_at__isnull=True,
                visit__client_id=request.user.pk,
            ).update(note=data['note'], due_at=data['due_at'], revision=F('revision') + 1):
                raise Conflict('Relance modifiée ou déjà programmée : rechargez.')
            event(
                original.visit.prospect,
                request.user,
                'client_followup_updated',
                data['note'],
                {
                    'follow_up_id': original.pk,
                    'due_at': data['due_at'].isoformat() if data['due_at'] else None,
                },
            )
        return self.retrieve(request, pk)

    @action(detail=True, methods=['get'])
    def prospect(self, request, pk=None):
        row = self.get_object().visit.prospect
        response = Response(
            {
                'id': row.pk,
                'name': row.name,
                'raw_phone': row.raw_phone,
                'revision': row.assignment_revision,
                'assigned_setter': None
                if row.assigned_setter_id is None
                else {
                    'id': row.assigned_setter_id,
                    'name': row.assigned_setter_name,
                },
            }
        )
        response['Cache-Control'] = 'no-store'
        return response


def sync_client_followup(visit, report):
    active = not report.performed and report.follow_up_owner == 'client'
    row = IsolationClientFollowUp.objects.filter(visit=visit).first()
    if not active:
        if row and row.closed_at is None:
            row.closed_at = timezone.now()
            row.revision += 1
            row.save(update_fields=['closed_at', 'revision'])
        return
    if row and row.programmed_visit_id:
        raise Conflict('Une nouvelle visite est déjà programmée depuis cette relance.')
    if row is None:
        IsolationClientFollowUp.objects.create(
            visit=visit,
            reason=report.absence_reason,
            note=report.note,
            due_at=report.follow_up_at,
        )
    else:
        row.closed_at = None
        row.reason = report.absence_reason
        row.note = report.note
        row.due_at = report.follow_up_at
        row.revision += 1
        row.save(update_fields=['closed_at', 'reason', 'note', 'due_at', 'revision'])


def due_notices():
    for row in (
        IsolationClientFollowUp.objects.filter(
            closed_at__isnull=True,
            due_at__lte=timezone.now(),
        )
        .select_related('visit')
        .iterator(chunk_size=200)
    ):
        key = hashlib.sha256(f'personal:{row.pk}:{row.due_at.isoformat()}'.encode()).hexdigest()
        IsolationNotice.objects.get_or_create(
            event_key=key,
            defaults={
                'visit': row.visit,
                'recipient_id': row.visit.client_id,
                'recipient_role': 'client',
                'kind': 'personal_followup',
                'anchor_at': row.due_at,
            },
        )
