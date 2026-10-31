"""Business status derived from explicit reports, cancellation and reschedule evidence."""

from django.utils import timezone
from rest_framework.exceptions import ValidationError

LABELS = {
    'scheduled': 'Planifié',
    'rescheduled': 'Reprogrammé',
    'performed': 'Rendez-vous validé',
    'absent': 'Non honoré',
    'not_performed': 'Non effectué — autre motif',
    'report_due': 'À renseigner',
    'cancelled': 'Annulé',
}


def report_outcome(report):
    if report.performed:
        return 'performed'
    return 'absent' if report.outcome == 'absent' else 'not_performed'


def output(row, now=None):
    now = now or timezone.now()
    if row.status == 'cancelled':
        state = 'cancelled'
    elif hasattr(row, 'report'):
        state = report_outcome(row.report)
    elif row.ends_at <= now:
        state = 'report_due'
    elif row.reschedule_count:
        state = 'rescheduled'
    else:
        state = 'scheduled'
    return {
        'business_status': state,
        'business_status_label': LABELS[state],
        'reschedule_count': row.reschedule_count,
        'rescheduled_at': row.rescheduled_at,
    }


def filter_status(qs, state, now=None):
    if not state:
        return qs
    if state not in LABELS:
        raise ValidationError('Statut métier de rendez-vous invalide.')
    now = now or timezone.now()
    if state == 'cancelled':
        return qs.filter(status='cancelled')
    qs = qs.filter(status='scheduled')
    if state == 'performed':
        return qs.filter(report__performed=True)
    if state == 'absent':
        return qs.filter(report__performed=False, report__outcome='absent')
    if state == 'not_performed':
        return qs.filter(report__performed=False).exclude(report__outcome='absent')
    qs = qs.filter(report__isnull=True)
    if state == 'report_due':
        return qs.filter(ends_at__lte=now)
    qs = qs.filter(ends_at__gt=now)
    return (
        qs.filter(reschedule_count__gt=0)
        if state == 'rescheduled'
        else qs.filter(reschedule_count=0)
    )
