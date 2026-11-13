"""Active prospecting is a view of recorded facts, never a deletion."""

from django.db.models import Exists, OuterRef, Subquery, Case, When, Value, F, CharField
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import Appointment, ContactCallOutcome, FollowUpTask


def apply_queue(qs, mode):
    if not mode:
        return qs
    if mode not in ('active', 'all', 'callbacks'):
        raise ValidationError('File de prospection invalide.')
    last = ContactCallOutcome.objects.filter(contact_id=OuterRef('pk')).order_by(
        '-created_at', '-pk'
    )
    booking = Appointment.objects.filter(contact_id=OuterRef('pk'), status='scheduled')
    callback_open = FollowUpTask.objects.filter(contact_id=OuterRef('pk'), closed_at__isnull=True)
    qs = qs.annotate(
        _queue_result=Subquery(last.values('result')[:1]),
        _queue_callback_due=Subquery(last.values('task__due_at')[:1]),
        _queue_callback_open=Exists(callback_open),
        _queue_booking=Exists(booking),
    )
    qs = qs.annotate(
        _queue_reason=Case(
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
        return qs.filter(_queue_result='callback', _queue_callback_open=True)
    return qs
