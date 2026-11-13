"""Active prospecting is a view of recorded facts, never a deletion."""

from django.db.models import Exists, OuterRef, Subquery, Case, When, Value, F, CharField
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import Appointment, AppointmentReport, ContactCallOutcome, FollowUpTask


def call_block_reason(contact):
    """Permanent call exclusions for an explicit decline or attended appointment."""
    if ContactCallOutcome.objects.filter(contact=contact, result='not_interested').exists():
        return 'Ce prospect a indiqué ne pas être intéressé : appel interdit.'
    if AppointmentReport.objects.filter(
        appointment__contact=contact, performed=True
    ).exists():
        return 'Ce prospect s’est présenté à un rendez-vous : appel interdit.'
    return ''


def apply_queue(qs, mode):
    if not mode:
        return qs
    if mode not in ('active', 'all', 'callbacks'):
        raise ValidationError('File de prospection invalide.')
    last = ContactCallOutcome.objects.filter(contact_id=OuterRef('pk')).order_by(
        '-created_at', '-pk'
    )
    booking = Appointment.objects.filter(contact_id=OuterRef('pk'), status='scheduled')
    declined = ContactCallOutcome.objects.filter(
        contact_id=OuterRef('pk'), result='not_interested'
    )
    attended = AppointmentReport.objects.filter(
        appointment__contact_id=OuterRef('pk'), performed=True
    )
    callback_open = FollowUpTask.objects.filter(contact_id=OuterRef('pk'), closed_at__isnull=True)
    qs = qs.annotate(
        _queue_result=Subquery(last.values('result')[:1]),
        _queue_callback_due=Subquery(last.values('task__due_at')[:1]),
        _queue_callback_open=Exists(callback_open),
        _queue_booking=Exists(booking),
        _queue_declined=Exists(declined),
        _queue_attended=Exists(attended),
    )
    qs = qs.annotate(
        _queue_reason=Case(
            When(_queue_declined=True, then=Value('not_interested')),
            When(_queue_attended=True, then=Value('appointment_attended')),
            When(_queue_booking=True, then=Value('appointment_booked')),
            When(
                _queue_result='callback',
                _queue_callback_due__gt=timezone.now(),
                then=Value('callback_pending'),
            ),
            When(_queue_result__isnull=False, then=F('_queue_result')),
            default=Value(''),
            output_field=CharField(),
        )
    )
    if mode == 'active':
        return qs.filter(_queue_reason='')
    if mode == 'callbacks':
        return qs.filter(
            _queue_result='callback',
            _queue_callback_open=True,
            _queue_declined=False,
            _queue_attended=False,
            _queue_booking=False,
        )
    return qs
