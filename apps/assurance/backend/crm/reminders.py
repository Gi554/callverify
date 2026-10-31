"""Periodic reminders: current period only, never infer a negative appointment result."""

import hashlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from .models import ReminderPolicy, ReminderEvent, FollowUpTask, Appointment, BusinessAudit
from .leases import Conflict

FIELDS = (
    'tasks_enabled',
    'reports_enabled',
    'task_interval_hours',
    'report_grace_hours',
    'report_cutoff_time',
    'report_interval_hours',
    'escalations_enabled',
    'task_escalation_hours',
    'report_escalation_hours',
    'escalation_interval_hours',
    'revision',
)
ESCALATIONS = ('task_escalation', 'report_escalation')
LABELS = {
    'task_overdue': 'Tâche en retard',
    'report_missing': 'Compte rendu manquant',
    'task_escalation': 'Escalade : tâche durablement en retard',
    'report_escalation': 'Escalade : compte rendu toujours manquant',
}


def policy():
    return ReminderPolicy.objects.filter(pk=1).first() or ReminderPolicy(pk=1)


def output_policy(row):
    result = {key: getattr(row, key) for key in FIELDS}
    result['report_cutoff_time'] = row.report_cutoff_time.strftime('%H:%M')
    return result


def report_deadline(appointment, rules):
    """Next calendar day in Québec, including daylight-saving transitions."""
    zone = ZoneInfo('America/Toronto')
    day = appointment.starts_at.astimezone(zone).date() + timedelta(days=1)
    deadline = datetime.combine(day, rules.report_cutoff_time, zone)
    # Legacy long meetings must have ended before any report is requested.
    if deadline <= appointment.ends_at:
        day = appointment.ends_at.astimezone(zone).date()
        deadline = datetime.combine(day, rules.report_cutoff_time, zone)
        if deadline <= appointment.ends_at:
            deadline = datetime.combine(day + timedelta(days=1), rules.report_cutoff_time, zone)
    return deadline


def active():
    rules = policy()
    now = timezone.now()
    conditions = Q(pk__in=[])
    if rules.tasks_enabled:
        conditions |= Q(
            kind='task_overdue',
            task__closed_at__isnull=True,
            task__due_at=F('anchor_at'),
            task__due_at__lte=now,
            task__setter_id=F('recipient_id'),
        )
    if rules.reports_enabled:
        reports = Q(
            kind='report_missing',
            appointment__status='scheduled',
            appointment__report__isnull=True,
            appointment__ends_at=F('anchor_at'),
            not_before__lte=now,
            appointment__advisor_id=F('recipient_id'),
        )
        if rules.report_reminders_from:
            reports &= Q(appointment__ends_at__gte=rules.report_reminders_from)
        conditions |= reports
    if rules.escalations_enabled and rules.tasks_enabled:
        conditions |= Q(
            kind='task_escalation',
            task__closed_at__isnull=True,
            task__due_at=F('anchor_at'),
            task__due_at__lte=now - timedelta(hours=rules.task_escalation_hours),
        )
    if rules.escalations_enabled and rules.reports_enabled:
        conditions |= Q(
            kind='report_escalation',
            appointment__status='scheduled',
            appointment__report__isnull=True,
            appointment__ends_at=F('anchor_at'),
            not_before__lte=now,
        )
    return ReminderEvent.objects.filter(
        conditions, policy_revision=rules.revision, valid_until__gt=now
    )


def generate():
    now = timezone.now()
    counts = {'created': 0, 'existing': 0, 'obsolete': 0}
    # Streaming full scans avoid starving later rows when earlier reminders already exist.
    for kind, ids in [
        (
            'task_overdue',
            FollowUpTask.objects.filter(closed_at__isnull=True, due_at__lte=now).values_list(
                'pk', flat=True
            ),
        ),
        (
            'report_missing',
            Appointment.objects.filter(
                status='scheduled', ends_at__lte=now, report__isnull=True
            ).values_list('pk', flat=True),
        ),
        (
            'task_escalation',
            FollowUpTask.objects.filter(closed_at__isnull=True, due_at__lte=now).values_list(
                'pk', flat=True
            ),
        ),
        (
            'report_escalation',
            Appointment.objects.filter(
                status='scheduled', ends_at__lte=now, report__isnull=True
            ).values_list('pk', flat=True),
        ),
    ]:
        for pk in ids.order_by('pk').iterator(chunk_size=200):
            with transaction.atomic():
                ReminderPolicy.objects.get_or_create(pk=1)
                ReminderPolicy.objects.filter(pk=1).update(revision=F('revision'))
                rules = ReminderPolicy.objects.get(pk=1)
                escalation = kind in ESCALATIONS
                if escalation and not rules.escalations_enabled:
                    continue
                if kind.startswith('task_'):
                    if not rules.tasks_enabled:
                        continue
                    FollowUpTask.objects.filter(pk=pk).update(revision=F('revision'))
                    row = FollowUpTask.objects.get(pk=pk)
                    if row.closed_at or row.due_at > now:
                        counts['obsolete'] += 1
                        continue
                    appointment = row.appointment
                    task = row
                    anchor = row.due_at
                    start = anchor
                    interval = rules.task_interval_hours
                    recipient = row.setter_id
                    role = 'setter'
                else:
                    if not rules.reports_enabled:
                        continue
                    Appointment.objects.filter(pk=pk).update(revision=F('revision'))
                    row = Appointment.objects.get(pk=pk)
                    if row.status != 'scheduled' or hasattr(row, 'report'):
                        counts['obsolete'] += 1
                        continue
                    appointment = row
                    task = None
                    anchor = row.ends_at
                    start = report_deadline(row, rules)
                    interval = rules.report_interval_hours
                    recipient = row.advisor_id
                    role = 'advisor'
                if escalation:
                    start += timedelta(
                        hours=rules.task_escalation_hours if task else rules.report_escalation_hours
                    )
                    interval = rules.escalation_interval_hours
                    recipient = 0
                    role = 'administrator'
                if start > now:
                    continue
                period = int((now - start).total_seconds() // (interval * 3600))
                if kind == 'report_missing':
                    # One gentle nudge per meeting/recipient, even across policy revisions.
                    # Do not mail a backlog on activation or after a prolonged outage.
                    if rules.report_reminders_from and anchor < rules.report_reminders_from:
                        continue
                    valid_until = start + timedelta(days=7)
                    if valid_until <= now:
                        continue
                    identity = f'{kind}:{pk}:{recipient}:{anchor.isoformat()}:once'
                else:
                    valid_until = start + timedelta(hours=interval * (period + 1))
                    identity = (
                        f'{kind}:{pk}:{recipient}:{anchor.isoformat()}:{rules.revision}:{period}'
                    )
                key = hashlib.sha256(identity.encode()).hexdigest()
                event, created = ReminderEvent.objects.get_or_create(
                    event_key=key,
                    defaults={
                        'kind': kind,
                        'appointment': appointment,
                        'task': task,
                        'recipient_id': recipient,
                        'recipient_role': role,
                        'anchor_at': anchor,
                        'policy_revision': rules.revision,
                        'valid_until': valid_until,
                        'not_before': start,
                    },
                )
                if not created and kind == 'report_missing':
                    # Keep the same event/relay identity after policy changes: no second mail.
                    ReminderEvent.objects.filter(pk=event.pk).update(
                        not_before=start, valid_until=valid_until, policy_revision=rules.revision
                    )
                counts['created' if created else 'existing'] += 1
                # No actor is invented for an automatic action; the event is its audit trail.
    return counts


class PolicyInput(serializers.Serializer):
    tasks_enabled = serializers.BooleanField()
    reports_enabled = serializers.BooleanField()
    task_interval_hours = serializers.IntegerField(min_value=1, max_value=720)
    report_grace_hours = serializers.IntegerField(min_value=0, max_value=720)
    report_cutoff_time = serializers.TimeField(required=False)

    def validate_report_cutoff_time(self, value):
        if value.second or value.microsecond:
            raise ValidationError('Heure et minutes uniquement')
        return value

    report_interval_hours = serializers.IntegerField(min_value=1, max_value=720)
    escalations_enabled = serializers.BooleanField()
    task_escalation_hours = serializers.IntegerField(min_value=1, max_value=2160)
    report_escalation_hours = serializers.IntegerField(min_value=1, max_value=2160)
    escalation_interval_hours = serializers.IntegerField(min_value=1, max_value=720)
    revision = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(max_length=1000)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés')
        return data


@api_view(['GET', 'POST'])
def configuration(request):
    if request.user.role != 'administrator':
        raise PermissionDenied('Règles de rappel réservées à l’administration Assurance')
    if request.method == 'GET':
        return Response(output_policy(policy()))
    serializer = PolicyInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    with transaction.atomic():
        ReminderPolicy.objects.get_or_create(pk=1)
        row = ReminderPolicy.objects.get(pk=1)
        before = output_policy(row)
        changes = {key: data.get(key, getattr(row, key)) for key in FIELDS if key != 'revision'}
        if not ReminderPolicy.objects.filter(pk=1, revision=data['revision']).update(
            **changes, revision=F('revision') + 1
        ):
            raise Conflict('Règles modifiées : actualisez')
        row.refresh_from_db()
        BusinessAudit.objects.create(
            actor_id=request.user.pk,
            object_id=1,
            action='policy.reminders_changed',
            metadata={'before': before, 'after': output_policy(row), 'reason': data['reason']},
        )
    return Response(output_policy(row))


@api_view(['GET'])
def reminders(request):
    qs = active()
    category = request.query_params.get('category', 'all')
    if category not in ('all', 'escalations'):
        raise ValidationError('Catégorie invalide')
    if category == 'escalations':
        if request.user.role != 'administrator':
            raise PermissionDenied('Escalades réservées à l’administration Assurance')
        qs = qs.filter(kind__in=ESCALATIONS)
    if request.user.role != 'administrator':
        qs = qs.filter(recipient_id=request.user.pk, recipient_role=request.user.role)
    pager = PageNumberPagination()
    pager.page_size = 25
    rows = pager.paginate_queryset(qs.order_by('-created_at', '-pk'), request)
    response = pager.get_paginated_response(
        [
            {
                'id': row.pk,
                'kind': row.kind,
                'label': LABELS[row.kind],
                'task_id': row.task_id,
                'appointment_id': row.appointment_id,
                'created_at': row.created_at,
                'valid_until': row.valid_until,
            }
            for row in rows
        ]
    )
    response['Cache-Control'] = 'no-store'
    return response
