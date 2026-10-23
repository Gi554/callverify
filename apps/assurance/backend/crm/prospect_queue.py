"""Active prospecting is a view of recorded facts, never a deletion."""

from django.db.models import Exists, OuterRef, Subquery, Case, When, Value, F, CharField
from rest_framework.exceptions import ValidationError
from .models import Appointment, ContactCallOutcome


def apply_queue(qs, mode):
    if not mode:
        return qs
    if mode not in ('active', 'all'):
        raise ValidationError('File de prospection invalide.')
    last = ContactCallOutcome.objects.filter(contact_id=OuterRef('pk')).order_by(
        '-created_at', '-pk'
    )
    booking = Appointment.objects.filter(contact_id=OuterRef('pk'), status='scheduled')
    qs = qs.annotate(
        _queue_result=Subquery(last.values('result')[:1]), _queue_booking=Exists(booking)
    )
    qs = qs.annotate(
        _queue_reason=Case(
            When(_queue_booking=True, then=Value('appointment_booked')),
            When(
                _queue_result__in=('appointment_booked', 'not_interested'), then=F('_queue_result')
            ),
            default=Value(''),
            output_field=CharField(),
        )
    )
    return qs.filter(_queue_reason='') if mode == 'active' else qs
