"""A single setter's live assigned inventory and appointment-start cohort."""

from django.db.models import Count, Q, Max
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from .quebec_period import ZONE, period
from .stats_series import daily

OUTCOMES = {
    'appointment_booked': 'Rendez-vous pris',
    'voicemail': 'Répondeur',
    'invalid_number': 'Numéro non attribué',
    'disconnected': 'Appel coupé',
    'not_interested': 'Pas intéressé',
    'callback': 'A demandé à être rappelé',
    'unreachable': 'Injoignable',
    'other': 'Autre résultat',
}


def performance(store, request, agent=None):
    if request.user.role not in ('administrator', 'setter'):
        raise PermissionDenied('Performance réservée aux setters et administrateurs.')
    if request.user.role == 'setter' and agent is not None and agent != request.user.pk:
        raise PermissionDenied('Votre performance uniquement.')
    names = store.Roster.roster()
    assigned = store.Contact.objects.exclude(assigned_setter_id=None)
    if request.user.role == 'setter':
        assigned = assigned.filter(assigned_setter_id=request.user.pk)
    latest = assigned.order_by().values('assigned_setter_id').annotate(last=Max('pk'))
    if latest.count() > 500:
        raise ValidationError('Annuaire limité à 500 agents.')
    names.update(
        dict(
            assigned.filter(pk__in=[item['last'] for item in latest]).values_list(
                'assigned_setter_id', 'assigned_setter_name'
            )
        )
    )
    if agent is None and request.user.role == 'administrator':
        if len(names) > 500:
            raise ValidationError('Annuaire limité à 500 agents.')
        result = Response(
            {
                'agents': [
                    {'id': pk, 'name': name or f'Setter #{pk}'}
                    for pk, name in sorted(names.items())
                ]
            }
        )
        result['Cache-Control'] = 'no-store'
        return result
    agent = agent or request.user.pk
    if agent not in names and agent != request.user.pk:
        raise ValidationError('Setter connu de cet espace requis.')
    start, end, lower, upper = period(request.query_params)
    inventory = store.Contact.objects.filter(assigned_setter_id=agent)
    meetings = store.Meeting.objects.filter(
        setter_id=agent, starts_at__gte=lower, starts_at__lt=upper
    )
    now = timezone.now()
    valid = Q(status='scheduled', ends_at__lte=now)
    held = valid & Q(**{store.result + '__performed': True})
    metrics = {
        'scheduled': Count('pk', filter=Q(status='scheduled')),
        'upcoming': Count('pk', filter=Q(status='scheduled', starts_at__gte=now)),
        'in_progress': Count(
            'pk', filter=Q(status='scheduled', starts_at__lt=now, ends_at__gt=now)
        ),
        'cancelled': Count('pk', filter=Q(status='cancelled')),
        'held': Count('pk', filter=held),
        'closed': Count('pk', filter=held & Q(**{store.result + '__' + store.closed_field: True})),
        'not_closed': Count(
            'pk', filter=held & Q(**{store.result + '__' + store.closed_field: False})
        ),
        'sale_unknown': Count(
            'pk', filter=held & Q(**{store.result + '__' + store.closed_field + '__isnull': True})
        ),
        'not_held': Count('pk', filter=valid & Q(**{store.result + '__performed': False})),
        'awaiting_result': Count('pk', filter=valid & Q(**{store.result + '__isnull': True})),
    }
    totals = meetings.aggregate(**metrics)
    totals['booked'] = store.Meeting.objects.filter(
        setter_id=agent, created_at__gte=lower, created_at__lt=upper
    ).count()
    outcomes = dict(
        store.outcomes(agent, lower, upper)
        .order_by()
        .values('result')
        .annotate(count=Count('pk'))
        .values_list('result', 'count')
    )
    totals['assigned_now'] = inventory.count()
    totals['current_assignments_in_period'] = inventory.filter(
        assigned_at__gte=lower, assigned_at__lt=upper
    ).count()
    totals['qualified'] = (
        meetings.exclude(**{store.snapshot: {}})
        .values(store.contact_field + '_id')
        .distinct()
        .count()
    )
    series = daily(meetings, start, end, ZONE, **metrics)
    result = Response(
        {
            'agent_id': agent,
            'agent_name': names.get(agent) or f'Setter #{agent}',
            'from': start,
            'to': end,
            'timezone': 'America/Toronto',
            'totals': totals,
            'daily': series,
            'outcomes': [
                {'key': key, 'label': label, 'count': outcomes.get(key, 0)}
                for key, label in OUTCOMES.items()
            ],
            'definition': 'Rendez-vous pris selon leur date de création au Québec, même si leur date prévue est hors période. Les autres compteurs de rendez-vous suivent leur date prévue dans la période et le setter à la réservation. À présenter : début à venir. Présentés et non tenus : résultat déclaré après la fin. Résultats attendus : rendez-vous terminé sans compte rendu. Les résultats d’appel suivent leur date de saisie et leur auteur. Inventaire affecté : état actuel. Qualifiés : fiches distinctes avec qualification capturée dans un rendez-vous de la période.',
        }
    )
    result['Cache-Control'] = 'no-store'
    return result
