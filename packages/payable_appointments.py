"""Appointments to pay for, read from the ledger of confirmed attendances.

Nothing is priced or paid here: the platform only counts, per setter and per period, the
appointments whose attendance was confirmed. Money stays outside.

An appointment is counted once, in the period containing the date the attendance was confirmed
(not its planned date). A period already closed never changes; a late confirmation or correction
is counted in the current period. See `payable_ledger`.
"""

from django.db.models import Count, Max, Q
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from .quebec_period import period

KIND_LABELS = {
    'counted': 'Comptabilisé',
    'withdrawn': 'Présence retirée (même semaine)',
    'withdrawn_after_week': 'Présence retirée après la clôture de la semaine',
    'sale_status_changed': 'Statut de vente modifié',
}
SALE_LABELS = {'closed': 'Closé', 'not_closed': 'Non closé'}


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
    entries = store.Entry.objects.filter(
        counted_at__gte=lower, counted_at__lt=upper, withdrawn_at__isnull=True
    )
    if agent is not None:
        entries = entries.filter(setter_id=agent)
    metrics = {'presented': Count('pk')}
    if store.split_sales:
        metrics['closed'] = Count('pk', filter=Q(closed_at_count=True))
        metrics['not_closed'] = Count('pk', filter=Q(closed_at_count=False))
    rows = list(
        entries.order_by()
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
    people, changes = {}, []
    if request.user.role == 'administrator':
        people = dict(
            store.Entry.objects.order_by()
            .values('setter_id')
            .annotate(name=Max('setter_name'))
            .values_list('setter_id', 'name')
        )
        history = store.History.objects.filter(
            created_at__gte=lower, created_at__lt=upper
        ).select_related('entry')
        if agent is not None:
            history = history.filter(entry__setter_id=agent)
        for item in history.order_by('-created_at', '-pk')[:50]:
            parent = getattr(item.entry, store.parent + '_id')
            changes.append(
                {
                    'id': item.pk,
                    'kind': item.kind,
                    'label': KIND_LABELS.get(item.kind, item.kind),
                    'appointment_id': parent,
                    'agent_name': item.entry.setter_name or f'Setter #{item.entry.setter_id}',
                    'before': SALE_LABELS.get(item.old_value, item.old_value),
                    'after': SALE_LABELS.get(item.new_value, item.new_value),
                    'late': item.late,
                    'at': item.created_at,
                    'counted_at': item.entry.counted_at,
                }
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
            'changes': changes,
            'definition': (
                'Un rendez-vous est compté une seule fois, dans la semaine (lundi au dimanche, '
                'heure du Québec) où sa présence a été confirmée, quelle que soit sa date prévue. '
                'Une semaine déjà payée ne change plus : une confirmation ou une correction '
                'tardive est comptée dans la semaine en cours. Sans présence confirmée, un '
                'rendez-vous n’est pas payable.'
                + (
                    ' Closé ou non closé est le statut au moment du décompte : une vente conclue '
                    'plus tard est suivie dans l’historique, sans créer de nouveau rendez-vous '
                    'payable ni modifier la semaine déjà comptée.'
                    if store.split_sales
                    else ''
                )
            ),
        }
    )
    response['Cache-Control'] = 'no-store'
    return response
