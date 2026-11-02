"""Appointments to pay for, counted from the results the team really recorded.

Nothing is priced or paid here: the platform only counts, per setter and per period, the
appointments the prospect attended and the advisor or client validated. Money stays outside.
"""

from django.db.models import Count, Max, Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from .quebec_period import period


def payable(store, request):
    if request.user.role not in ('administrator', 'setter'):
        raise PermissionDenied('Rendez-vous payables réservés aux setters et administrateurs.')
    start, end, lower, upper = period(request.query_params)
    agent = request.query_params.get('agent', '')
    try:
        agent = int(agent) if agent else None
    except ValueError:
        raise ValidationError({'agent': 'Identifiant de setter invalide.'}) from None
    if request.user.role == 'setter':
        if agent not in (None, request.user.pk):
            raise PermissionDenied('Vos rendez-vous uniquement.')
        agent = request.user.pk
    meetings = store.Meeting.objects.filter(starts_at__gte=lower, starts_at__lt=upper)
    if agent is not None:
        meetings = meetings.filter(setter_id=agent)
    # Final result only: a rescheduled appointment is one row at its new time, a cancelled one
    # is not payable, and a missing or negative result never counts.
    held = Q(status='scheduled', ends_at__lte=timezone.now()) & Q(
        **{store.result + '__performed': True}
    )
    metrics = {'presented': Count('pk', filter=held)}
    if store.split_sales:
        sale = store.result + '__' + store.closed_field
        metrics['closed'] = Count('pk', filter=held & Q(**{sale: True}))
        metrics['not_closed'] = Count('pk', filter=held & ~Q(**{sale: True}))
    rows = list(
        meetings.order_by()
        .values('setter_id')
        .annotate(name=Max('setter_name'), **metrics)
        .order_by('name', 'setter_id')
    )
    if len(rows) > 500:
        raise ValidationError('Annuaire limité à 500 agents.')

    def output(row):
        result = {
            'agent_id': row['setter_id'],
            'agent_name': row['name'] or f'Setter #{row["setter_id"]}',
            'presented': row['presented'],
        }
        if store.split_sales:
            result['closed'] = row['closed']
            result['not_closed'] = row['not_closed']
        result['payable'] = (
            row['closed'] + row['not_closed'] if store.split_sales else row['presented']
        )
        return result

    rows = [output(row) for row in rows]
    keys = ['presented', 'payable'] + (['closed', 'not_closed'] if store.split_sales else [])
    totals = {key: sum(row[key] for row in rows) for key in keys}
    people = (
        {}
        if request.user.role != 'administrator'
        else dict(
            store.Meeting.objects.order_by()
            .values('setter_id')
            .annotate(name=Max('setter_name'))
            .values_list('setter_id', 'name')
        )
    )
    response = Response(
        {
            'from': start,
            'to': end,
            'timezone': 'America/Toronto',
            'split_sales': store.split_sales,
            'agent_id': agent,
            'agents': [
                {'id': pk, 'name': name or f'Setter #{pk}'} for pk, name in sorted(people.items())
            ],
            'totals': totals,
            'rows': rows,
            'definition': (
                'Rendez-vous selon leur date de début (heure du Québec) et le setter qui les a '
                'réservés. Seuls comptent les rendez-vous non annulés, terminés, dont le prospect '
                'est déclaré présent. Un rendez-vous reprogrammé compte une fois, à sa nouvelle '
                'date ; sans résultat déclaré, il ne compte pas.'
            ),
        }
    )
    response['Cache-Control'] = 'no-store'
    return response
