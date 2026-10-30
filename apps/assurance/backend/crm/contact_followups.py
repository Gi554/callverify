"""Setter-declared outcomes and contact callbacks; never initiates a call."""

import hashlib
import json
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from .models import ContactCallOutcome, FollowUpTask, Appointment, BusinessAudit
from .agreements import lock_contact
from .leases import Conflict
from .notifications import notify

RESULTS = dict(ContactCallOutcome._meta.get_field('result').choices)


def explicit_future(value):
    try:
        parsed = parse_datetime(str(value))
    except (ValueError, TypeError):
        parsed = None
    if parsed is None or timezone.is_naive(parsed) or parsed <= timezone.now():
        raise ValidationError('Date et heure futures avec décalage explicite requises.')


class Strict(serializers.Serializer):
    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés.')
        return data


class TaskFields(Strict):
    due_at = serializers.DateTimeField()
    reason = serializers.CharField(max_length=3000, allow_blank=True, default='')
    priority = serializers.ChoiceField(
        choices=['low', 'normal', 'high', 'urgent'], default='normal'
    )

    def validate(self, data):
        data = super().validate(data)
        explicit_future(self.initial_data['due_at'])
        return data


class TaskCreate(TaskFields):
    token = serializers.UUIDField(write_only=True)
    contact_revision = serializers.IntegerField(min_value=0)
    request_id = serializers.UUIDField()


class TaskEdit(TaskFields):
    revision = serializers.IntegerField(min_value=0)


class OutcomeInput(Strict):
    token = serializers.UUIDField(write_only=True)
    contact_revision = serializers.IntegerField(min_value=0)
    request_id = serializers.UUIDField()
    result = serializers.ChoiceField(choices=RESULTS)
    note = serializers.CharField(max_length=3000, allow_blank=True, default='')
    due_at = serializers.DateTimeField(required=False)
    appointment_id = serializers.IntegerField(min_value=1, required=False)

    def validate(self, data):
        data = super().validate(data)
        if data['result'] == 'callback':
            if 'due_at' not in data:
                raise ValidationError('Date et heure du rappel requises.')
            explicit_future(self.initial_data['due_at'])
        elif 'due_at' in data:
            raise ValidationError('Échéance réservée au résultat Rappel.')
        if (data['result'] == 'appointment_booked') != ('appointment_id' in data):
            raise ValidationError(
                'Un rendez-vous enregistré est requis uniquement pour Rendez-vous pris.'
            )
        return data


def fingerprint(data):
    return hashlib.sha256(
        json.dumps(
            {
                k: str(v)
                for k, v in data.items()
                if k not in ('token', 'contact_revision', 'request_id')
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()


def own_replay(row, contact, user, digest):
    if row.contact_id != contact.pk or row.setter_id != user.pk or row.fingerprint != digest:
        raise Conflict('Cet identifiant correspond déjà à une autre saisie.')


def outcome_output(row):
    return {
        'id': row.pk,
        'result': row.result,
        'label': RESULTS[row.result],
        'note': row.note,
        'appointment_id': row.appointment_id,
        'task_id': row.task_id,
        'created_at': row.created_at,
        'source': 'setter_declared',
    }


def audit_task(row, user, action, metadata):
    BusinessAudit.objects.create(
        actor_id=user.pk,
        object_id=row.appointment_id or row.contact_id,
        action=('appointment' if row.appointment_id else 'contact') + '.' + action,
        metadata={'task_id': row.pk, **metadata},
    )


class ContactFollowUpMixin:
    @action(detail=True, methods=['get', 'post'], url_path='call-outcomes')
    def call_outcomes(self, request, pk=None):
        if request.user.role not in ('setter', 'administrator'):
            raise PermissionDenied('Résultats d’appel internes.')
        contact = self.get_object()
        if request.method == 'GET':
            qs = contact.call_outcomes.order_by('-created_at', '-pk')
            if request.user.role == 'setter':
                qs = qs.filter(setter_id=request.user.pk)
            return self.get_paginated_response(
                [outcome_output(row) for row in self.paginate_queryset(qs)]
            )
        serializer = OutcomeInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        digest = fingerprint(data)
        with transaction.atomic():
            current = lock_contact(contact, request.user, data, check_revision=False)
            existing = ContactCallOutcome.objects.filter(request_id=data['request_id']).first()
            if existing:
                own_replay(existing, contact, request.user, digest)
                return Response({**outcome_output(existing), 'contact_revision': current.revision})
            if current.revision != data['contact_revision']:
                raise Conflict('Fiche modifiée : rechargez.')
            appointment = None
            task = None
            if data['result'] == 'appointment_booked':
                appointments = Appointment.objects.filter(
                    pk=data['appointment_id'], contact=contact, status='scheduled'
                )
                if request.user.role == 'setter':
                    appointments = appointments.filter(setter_id=request.user.pk)
                appointment = appointments.first()
                if appointment is None:
                    raise ValidationError('Rendez-vous planifié et autorisé de ce contact requis.')
            if data['result'] == 'callback':
                task = FollowUpTask.objects.create(
                    contact=contact,
                    setter_id=request.user.pk,
                    due_at=data['due_at'],
                    reason=data['note'] or 'Rappel demandé par le prospect',
                )
                audit_task(task, request.user, 'follow_up_created', {'source': 'call_result'})
                notify(task, 'manual', f'manual:{task.pk}')
            row = ContactCallOutcome.objects.create(
                contact=contact,
                setter_id=request.user.pk,
                request_id=data['request_id'],
                fingerprint=digest,
                result=data['result'],
                note=data['note'],
                appointment=appointment,
                task=task,
            )
            BusinessAudit.objects.create(
                actor_id=request.user.pk,
                object_id=contact.pk,
                action='contact.call_outcome_recorded',
                metadata={'outcome_id': row.pk, 'result': row.result, 'task_id': row.task_id},
            )
            return Response(
                {**outcome_output(row), 'contact_revision': current.revision}, status=201
            )

    @action(detail=True, methods=['get', 'post'], url_path='follow-ups')
    def contact_follow_ups(self, request, pk=None):
        from .reports import task_output

        if request.user.role not in ('setter', 'administrator'):
            raise PermissionDenied('Rappels internes.')
        contact = self.get_object()
        if request.method == 'GET':
            qs = (
                FollowUpTask.objects.filter(Q(contact=contact) | Q(appointment__contact=contact))
                .select_related('contact', 'appointment__contact')
                .order_by('closed_at', 'due_at', 'pk')
            )
            if request.user.role == 'setter':
                qs = qs.filter(setter_id=request.user.pk)
            return self.get_paginated_response(
                [task_output(row, request.user) for row in self.paginate_queryset(qs)]
            )
        serializer = TaskCreate(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        digest = fingerprint(data)
        with transaction.atomic():
            current = lock_contact(contact, request.user, data, check_revision=False)
            existing = FollowUpTask.objects.filter(request_id=data['request_id']).first()
            if existing:
                own_replay(existing, contact, request.user, digest)
                return Response(task_output(existing, request.user))
            if current.revision != data['contact_revision']:
                raise Conflict('Fiche modifiée : rechargez.')
            row = FollowUpTask.objects.create(
                contact=contact,
                setter_id=request.user.pk,
                request_id=data['request_id'],
                fingerprint=digest,
                due_at=data['due_at'],
                reason=data['reason'],
                priority=data['priority'],
            )
            audit_task(row, request.user, 'follow_up_created', {'source': 'manual'})
            notify(row, 'manual', f'manual:{row.pk}')
            return Response(task_output(row, request.user), status=201)
