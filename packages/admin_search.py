"""Scoped administrative search with same-row appointment criteria and exact exports."""

from django.db.models import Q, F, Value, OuterRef, Subquery, Exists, Case, When, CharField
from django.db.models.functions import Replace
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from .quebec_period import ZONE, period
from .stat_filters import options
from .exports import kind, bounded, response as export_response

STATES = {
    'scheduled': 'Planifié (tous)',
    'held': 'Rendez-vous tenu',
    'closed': 'Vente conclue',
    'not_closed': 'Vente non conclue',
    'sale_unknown': 'Résultat commercial attendu',
    'not_held': 'Rendez-vous non tenu',
    'absent': 'Absence déclarée',
    'cancelled': 'Annulé',
    'report_due': 'Compte rendu attendu',
}


class Filters(serializers.Serializer):
    name = serializers.CharField(max_length=250, required=False)
    phone = serializers.CharField(max_length=100, required=False)
    owner_id = serializers.IntegerField(min_value=1, max_value=9223372036854775807, required=False)
    setter_id = serializers.IntegerField(min_value=1, max_value=9223372036854775807, required=False)
    target_id = serializers.IntegerField(min_value=1, max_value=9223372036854775807, required=False)
    campaign_id = serializers.IntegerField(
        min_value=1, max_value=9223372036854775807, required=False
    )
    appointment_id = serializers.IntegerField(
        min_value=1, max_value=9223372036854775807, required=False
    )
    contact_status = serializers.CharField(max_length=40, required=False)
    appointment_status = serializers.ChoiceField(choices=list(STATES), required=False)
    from_date = serializers.DateField(required=False)
    to_date = serializers.DateField(required=False)


def statuses(store, rows):
    relation = store.result
    return rows.annotate(
        _search_status=Case(
            When(status='cancelled', then=Value('cancelled')),
            When(
                **{relation + '__performed': True, relation + '__' + store.closed_field: True},
                then=Value('closed'),
            ),
            When(
                **{relation + '__performed': True, relation + '__' + store.closed_field: False},
                then=Value('not_closed'),
            ),
            When(**{relation + '__performed': True}, then=Value('sale_unknown')),
            When(
                **{relation + '__performed': False, relation + '__outcome': 'absent'},
                then=Value('absent'),
            ),
            When(**{relation + '__performed': False}, then=Value('not_held')),
            When(ends_at__lte=timezone.now(), then=Value('report_due')),
            default=Value('scheduled'),
            output_field=CharField(),
        )
    )


def queryset(store, data):
    contacts = store.Contact.objects.all()
    if data.get('name'):
        contacts = contacts.filter(name__icontains=data['name'])
    if data.get('phone'):
        number = ''.join(c for c in data['phone'] if c.isdigit())
        expr = F(store.phone)
        for char in (' ', '+', '-', '(', ')', '.'):
            expr = Replace(expr, Value(char), Value(''))
        contacts = (
            contacts.annotate(_normalized_phone=expr).filter(
                Q(**{store.phone + '__icontains': data['phone']})
                | Q(_normalized_phone__icontains=number)
            )
            if number
            else contacts.filter(**{store.phone + '__icontains': data['phone']})
        )
    if data.get('owner_id'):
        contacts = contacts.filter(assigned_setter_id=data['owner_id'])
    if data.get('contact_status') and data['contact_status'] not in store.contact_labels():
        raise ValidationError('Statut de fiche invalide.')
    if data.get('contact_status'):
        contacts = contacts.filter(**{store.contact_status: data['contact_status']})
    if data.get('campaign_id'):
        contacts = contacts.filter(**{store.campaign_id: data['campaign_id']})
    meetings = store.Meeting.objects.filter(**{store.contact_field + '_id': OuterRef('pk')})
    required = False
    for key, field in [
        ('setter_id', 'setter_id'),
        ('target_id', store.target + '_id'),
        ('appointment_id', 'pk'),
    ]:
        if data.get(key):
            meetings = meetings.filter(**{field: data[key]})
            required = True
    if bool(data.get('from_date')) != bool(data.get('to_date')):
        raise ValidationError('Les deux dates sont requises pour filtrer les rendez-vous.')
    if data.get('from_date'):
        _, _, lower, upper = period({'from': str(data['from_date']), 'to': str(data['to_date'])})
        meetings = meetings.filter(starts_at__gte=lower, starts_at__lt=upper)
        required = True
    state = data.get('appointment_status')
    if state:
        required = True
        if state in ('scheduled', 'cancelled'):
            meetings = meetings.filter(status=state)
        elif state in ('held', 'closed', 'not_closed', 'sale_unknown'):
            meetings = meetings.filter(status='scheduled', **{store.result + '__performed': True})
            if state != 'held':
                meetings = meetings.filter(
                    **{
                        store.result
                        + '__'
                        + store.closed_field
                        + ('__isnull' if state == 'sale_unknown' else ''): True
                        if state in ('closed', 'sale_unknown')
                        else False
                    }
                )
        elif state == 'report_due':
            meetings = meetings.filter(
                status='scheduled', ends_at__lte=timezone.now(), **{store.result + '__isnull': True}
            )
        else:
            meetings = meetings.filter(status='scheduled', **{store.result + '__performed': False})
            if state == 'absent':
                meetings = meetings.filter(**{store.result + '__outcome': 'absent'})
    if required:
        contacts = contacts.filter(Exists(meetings))
    latest = statuses(store, meetings).order_by('-starts_at', '-pk')
    fields = {
        'meeting_id': 'pk',
        'meeting_start': 'starts_at',
        'meeting_setter': 'setter_name',
        'meeting_setter_id': 'setter_id',
        'meeting_target': store.target + '_name',
        'meeting_target_id': store.target + '_id',
        'meeting_status': '_search_status',
    }
    return contacts.annotate(
        **{key: Subquery(latest.values(field)[:1]) for key, field in fields.items()}
    ).order_by('-pk')


def output(store, row):
    return {
        'id': row.pk,
        'name': row.name,
        'phone': getattr(row, store.phone),
        'contact_status': getattr(row, store.contact_status),
        'owner_id': row.assigned_setter_id,
        'owner_name': row.assigned_setter_name,
        'appointment_id': row.meeting_id,
        'starts_at': row.meeting_start,
        'setter_id': row.meeting_setter_id,
        'setter_name': row.meeting_setter,
        'target_id': row.meeting_target_id,
        'target_name': row.meeting_target,
        'appointment_status': row.meeting_status,
    }


def search(store, request):
    if request.user.role != 'administrator':
        raise PermissionDenied('Recherche réservée à l’administration de cet espace.')
    if set(request.query_params) - set(Filters().fields) - {'page', 'file'}:
        raise ValidationError('Filtre non autorisé.')
    serializer = Filters(
        data={k: v for k, v in request.query_params.items() if k not in ('page', 'file')}
    )
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    contacts = queryset(store, data)
    if request.query_params.get('file'):
        file = kind(request)
        rows = [output(store, r) for r in bounded(contacts, file)]
        labels = store.contact_labels()
        headers = [
            'Fiche ID',
            'Prospect',
            'Téléphone fourni',
            'Statut de la fiche',
            'Setter actuel',
            'Rendez-vous ID',
            'Début (Québec)',
            'Setter à la réservation',
            store.target_label,
            'Statut du rendez-vous',
        ]
        values = [
            [
                r['id'],
                r['name'],
                r['phone'],
                labels.get(r['contact_status'], r['contact_status']),
                r['owner_name'] or r['owner_id'],
                r['appointment_id'],
                r['starts_at'].astimezone(ZONE).replace(tzinfo=None) if r['starts_at'] else None,
                r['setter_name'],
                r['target_name'],
                STATES.get(r['appointment_status'], r['appointment_status']),
            ]
            for r in rows
        ]
        result = export_response(
            file, headers, values, 'recherche-' + store.workspace, 'Recherche ' + store.workspace
        )
        store.export_audit(
            request.user.pk,
            file,
            len(rows),
            {k: str(v) for k, v in data.items() if k not in ('name', 'phone')},
        )
        return result
    try:
        page = int(request.query_params.get('page', '1'))
        if not 1 <= page <= 1000000:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValidationError('Page invalide.') from None
    all_contacts = store.Contact.objects.all()
    all_meetings = store.Meeting.objects.all()
    people = {
        r['id']: r for r in options(all_contacts, 'assigned_setter_id', 'assigned_setter_name')
    }
    people.update({r['id']: r for r in options(all_meetings, 'setter_id', 'setter_name')})
    result = Response(
        {
            'count': contacts.count(),
            'results': [output(store, r) for r in contacts[(page - 1) * 25 : page * 25]],
            'page': page,
            'timezone': 'America/Toronto',
            'filters': data,
            'options': {
                'setters': sorted(people.values(), key=lambda r: r['name'].casefold())[:500],
                'targets': options(all_meetings, store.target + '_id', store.target + '_name'),
                'campaigns': options(all_contacts, store.campaign_id, store.campaign_name),
                'contact_statuses': [
                    {'id': key, 'name': label} for key, label in store.contact_labels().items()
                ],
                'appointment_statuses': [
                    {'id': key, 'name': label}
                    for key, label in STATES.items()
                    if key != 'absent' or store.workspace == 'assurance'
                ],
            },
            'definition': 'Le setter actuel filtre l’affectation présente. Setter de réservation, conseiller/client, identifiant, dates et statut doivent correspondre au même rendez-vous. La dernière rencontre correspondant aux critères est affichée ; la fiche reste visible sans rendez-vous lorsqu’aucun de ces critères n’est demandé.',
        }
    )
    result['Cache-Control'] = 'no-store'
    return result
