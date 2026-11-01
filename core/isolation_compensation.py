"""CAD accruals from explicit attendance/sale, one credit per commercial process and component."""

from datetime import timedelta
from decimal import Decimal
from django.core import signing
from django.db import transaction
from django.db.models import Q, F, Count, Sum, OuterRef, Subquery, Max
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from packages.access.isolation_events import verify
from packages.quebec_period import period
from .isolation_work import WorkAuthentication, Conflict, Pager
from .models import IsolationSetterRate, IsolationVisit, IsolationUnqualified, Prospect, AuditEvent


def admin(request):
    if request.user.role != 'administrator':
        raise PermissionDenied('Rémunération réservée à l’administration Isolation.')


def span(params):
    if params.get('week_of'):
        if params.get('from') or params.get('to'):
            raise ValidationError('Choisissez une semaine ou une période personnalisée.')
        try:
            day = parse_date(params['week_of'])
            start = day - timedelta(days=day.weekday())
            params = {'from': start.isoformat(), 'to': (start + timedelta(days=6)).isoformat()}
        except (ValueError, TypeError, AttributeError, OverflowError):
            raise ValidationError('Semaine invalide.') from None
    return period(params)


def money(value):
    return None if value is None else format(value, '.2f')


def rate_output(row):
    return {
        'id': row.pk,
        'setter_id': row.setter_id,
        'setter_name': row.setter_name,
        'client_id': row.client_id,
        'client_name': row.client_name,
        'currency': 'CAD',
        'attendance_cad': money(row.attendance_cad),
        'sale_bonus_cad': money(row.sale_bonus_cad),
        'revision': row.revision,
    }


def rate_claims(token, user):
    try:
        data = verify(token, 'compensation_rate')
        if (
            set(data) != {'actor', 'setter', 'client'}
            or type(data['actor']) is not int
            or data['actor'] != user.pk
        ):
            raise signing.BadSignature()
        for role in ('setter', 'client'):
            person = data[role]
            if (
                not isinstance(person, dict)
                or set(person) != {'id', 'name'}
                or type(person['id']) is not int
                or person['id'] <= 0
                or not isinstance(person['name'], str)
                or not 1 <= len(person['name']) <= 150
            ):
                raise signing.BadSignature()
        if data['setter']['id'] == data['client']['id']:
            raise signing.BadSignature()
        return data
    except (signing.BadSignature, TypeError, ValueError, KeyError):
        raise ValidationError('Attestation de tarif invalide ou expirée : rechargez.') from None


class RateInput(serializers.Serializer):
    proof = serializers.CharField(max_length=8192)
    attendance_cad = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, allow_null=True
    )
    sale_bonus_cad = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, allow_null=True
    )
    revision = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(max_length=1000)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés.')
        return data


@api_view(['GET', 'POST'])
@authentication_classes([WorkAuthentication])
@permission_classes([IsAuthenticated])
def rates(request):
    admin(request)
    if request.method == 'GET':
        rows = IsolationSetterRate.objects.order_by('client_id', 'setter_id')
        for field in ('setter_id', 'client_id'):
            value = request.query_params.get(field)
            if value is not None:
                if not value.isdigit() or int(value) <= 0:
                    raise ValidationError('Identifiant invalide.')
                rows = rows.filter(**{field: int(value)})
        pager = Pager()
        response = pager.get_paginated_response(
            [rate_output(row) for row in pager.paginate_queryset(rows, request)]
        )
    else:
        serializer = RateInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        claims = rate_claims(data['proof'], request.user)
        with transaction.atomic():
            row, _ = IsolationSetterRate.objects.get_or_create(
                setter_id=claims['setter']['id'],
                client_id=claims['client']['id'],
                defaults={
                    'setter_name': claims['setter']['name'],
                    'client_name': claims['client']['name'],
                },
            )
            before = rate_output(row)
            if not IsolationSetterRate.objects.filter(pk=row.pk, revision=data['revision']).update(
                attendance_cad=data['attendance_cad'],
                sale_bonus_cad=data['sale_bonus_cad'],
                setter_name=claims['setter']['name'],
                client_name=claims['client']['name'],
                revision=F('revision') + 1,
            ):
                raise Conflict('Tarif modifié : rechargez avant de sauvegarder.')
            row.refresh_from_db()
            AuditEvent.objects.create(
                action='isolation.compensation.rate_updated',
                object_id=str(row.pk),
                metadata={
                    'actor_portal_id': request.user.pk,
                    'reason': data['reason'],
                    'before': before,
                    'after': rate_output(row),
                },
            )
        response = Response(rate_output(row))
    response['Cache-Control'] = 'no-store'
    return response


def capture(visit, report, actor_id, rate=None):
    if not report.performed or visit.status != 'scheduled' or visit.ends_at > timezone.now():
        return False
    if rate is None:
        rate = IsolationSetterRate.objects.filter(
            setter_id=visit.setter_id, client_id=visit.client_id
        ).first()
    if rate is None:
        return False
    changed = {}
    for component, amount, eligible in (
        ('attendance', rate.attendance_cad, True),
        ('sale', rate.sale_bonus_cad, report.closed is True),
    ):
        if eligible and amount is not None and getattr(report, component + '_unit_cad') is None:
            setattr(report, component + '_unit_cad', amount)
            setattr(report, component + '_rate_revision', rate.revision)
            setattr(report, component + '_valued_at', timezone.now())
            changed[component] = {'unit_cad': money(amount), 'revision': rate.revision}
    if not changed:
        return False
    report.save(
        update_fields=[
            component + suffix
            for component in changed
            for suffix in ('_unit_cad', '_rate_revision', '_valued_at')
        ]
    )
    AuditEvent.objects.create(
        action='isolation.compensation.captured',
        object_id=str(visit.pk),
        metadata={
            'actor_portal_id': actor_id,
            'process_id': str(visit.process_id),
            'setter_id': visit.setter_id,
            'client_id': visit.client_id,
            'components': changed,
        },
    )
    return True


class ValueInput(serializers.Serializer):
    proof = serializers.CharField(max_length=8192)
    rate_revision = serializers.IntegerField(min_value=0)
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()
    reason = serializers.CharField(max_length=1000)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés.')
        return data


@api_view(['POST'])
@authentication_classes([WorkAuthentication])
@permission_classes([IsAuthenticated])
def value_missing(request):
    admin(request)
    serializer = ValueInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    claims = rate_claims(data['proof'], request.user)
    _, _, lower, upper = span({'from': str(data['starts_on']), 'to': str(data['ends_on'])})
    with transaction.atomic():
        rate = (
            IsolationSetterRate.objects.select_for_update()
            .filter(setter_id=claims['setter']['id'], client_id=claims['client']['id'])
            .first()
        )
        if rate is None or rate.revision != data['rate_revision']:
            raise Conflict('Tarif modifié ou absent : rechargez.')
        missing = Q(pk__in=[])
        if rate.attendance_cad is not None:
            missing |= Q(result__attendance_unit_cad__isnull=True)
        if rate.sale_bonus_cad is not None:
            missing |= Q(result__closed=True, result__sale_unit_cad__isnull=True)
        rows = IsolationVisit.objects.filter(
            missing,
            status='scheduled',
            result__performed=True,
            ends_at__lte=timezone.now(),
            setter_id=rate.setter_id,
            client_id=rate.client_id,
            starts_at__gte=lower,
            starts_at__lt=upper,
        )
        ids = list(rows.order_by('prospect_id', 'pk').values_list('pk', 'prospect_id')[:200])
        list(
            Prospect.objects.select_for_update()
            .filter(pk__in=[p for _, p in ids])
            .order_by('pk')
            .values_list('pk', flat=True)
        )
        valued = 0
        for visit in (
            rows.filter(pk__in=[v for v, _ in ids]).select_related('result').order_by('pk')
        ):
            valued += capture(visit, visit.result, request.user.pk, rate)
        remaining = rows.count()
        AuditEvent.objects.create(
            action='isolation.compensation.batch_valued',
            object_id=str(rate.pk),
            metadata={
                'actor_portal_id': request.user.pk,
                'reason': data['reason'],
                'from': str(data['starts_on']),
                'to': str(data['ends_on']),
                'rate_revision': rate.revision,
                'valued': valued,
                'remaining': remaining,
            },
        )
    return Response({'valued': valued, 'remaining': remaining})


def credited(component):
    candidates = IsolationVisit.objects.filter(
        process_id=OuterRef('process_id'),
        status='scheduled',
        result__performed=True,
        ends_at__lte=timezone.now(),
    )
    if component == 'sale':
        candidates = candidates.filter(result__closed=True)
    first = candidates.order_by('starts_at', 'pk').values('pk')[:1]
    return IsolationVisit.objects.annotate(_first=Subquery(first)).filter(pk=F('_first'))


def setter_payable(setter_id, params=None):
    """The same first-presence credit as admin payroll, without exposing any prices."""
    start, end, lower, upper = span(params or {})
    rows = credited('attendance').filter(
        setter_id=setter_id,
        prospect__assigned_setter_id=setter_id,
        starts_at__gte=lower,
        starts_at__lt=upper,
    )
    return {
        'from': start.isoformat(),
        'to': end.isoformat(),
        'timezone': 'America/Toronto',
        **rows.aggregate(
            payable=Count('pk'),
            presented_closed=Count('pk', filter=Q(result__closed=True)),
            presented_not_closed=Count('pk', filter=Q(result__closed=False)),
            sale_unknown=Count('pk', filter=Q(result__closed__isnull=True)),
        ),
    }


METRICS = {
    'programmed': Count('pk'),
    'attended': Count('pk', filter=Q(status='scheduled', result__performed=True)),
    'absent': Count(
        'pk',
        filter=Q(status='scheduled', result__performed=False) & ~Q(result__outcome='unqualified'),
    ),
    'unqualified_visits': Count('pk', filter=Q(result__outcome='unqualified')),
    'sales': Count('pk', filter=Q(status='scheduled', result__performed=True, result__closed=True)),
    'reprogrammed': Count('pk', filter=Q(previous_visit__isnull=False)),
    'cancelled': Count('pk', filter=Q(status='cancelled')),
    'sale_unknown': Count(
        'pk', filter=Q(status='scheduled', result__performed=True, result__closed__isnull=True)
    ),
}


def build(params):
    start, end, lower, upper = span(params)
    grouped = {}

    def merge(rows):
        for row in rows:
            key = (row['client_id'], row['setter_id'])
            grouped.setdefault(
                key,
                {
                    'client_id': key[0],
                    'setter_id': key[1],
                    'client_name': 'Client',
                    'setter_name': 'Setter',
                },
            ).update(row)

    fields = ('client_id', 'setter_id')
    visits = IsolationVisit.objects.filter(starts_at__gte=lower, starts_at__lt=upper)
    metrics = dict(
        METRICS,
        upcoming=Count(
            'pk', filter=Q(status='scheduled', starts_at__gt=timezone.now(), result__isnull=True)
        ),
        pending_results=Count(
            'pk',
            filter=Q(status='scheduled', ends_at__lte=timezone.now())
            & (Q(result__isnull=True) | Q(result__closed__isnull=True)),
        ),
    )
    merge(visits.values(*fields).annotate(**metrics))
    merge(
        IsolationUnqualified.objects.filter(created_at__gte=lower, created_at__lt=upper)
        .values(*fields)
        .annotate(unqualified=Count('pk'))
    )
    for component in ('attendance', 'sale'):
        rows = credited(component).filter(starts_at__gte=lower, starts_at__lt=upper)
        merge(
            rows.values(*fields).annotate(
                **{
                    component + '_credits': Count('pk'),
                    component + '_unpriced': Count(
                        'pk', filter=Q(**{'result__' + component + '_unit_cad__isnull': True})
                    ),
                    component + '_amount': Sum('result__' + component + '_unit_cad'),
                }
            )
        )
    for rate in IsolationSetterRate.objects.all():
        merge(
            [
                {
                    'client_id': rate.client_id,
                    'setter_id': rate.setter_id,
                    'client_name': rate.client_name,
                    'setter_name': rate.setter_name,
                    'rate_attendance_cad': money(rate.attendance_cad),
                    'rate_sale_bonus_cad': money(rate.sale_bonus_cad),
                    'rate_revision': rate.revision,
                }
            ]
        )
    if len(grouped) > 5000:
        raise ValidationError('Rapport limité à 5 000 groupes ; réduisez la période.')
    # Names are display-only snapshots. Identities, not names, define every aggregation.
    for model in (IsolationUnqualified, IsolationVisit):
        latest = (
            model.objects.filter(
                client_id__in={k[0] for k in grouped}, setter_id__in={k[1] for k in grouped}
            )
            .values(*fields)
            .annotate(last=Max('pk'))
            .values('last')
        )
        for row in model.objects.filter(pk__in=Subquery(latest)).values(
            *fields, 'client_name', 'setter_name'
        ):
            if (row['client_id'], row['setter_id']) in grouped:
                grouped[(row['client_id'], row['setter_id'])].update(
                    {k: row[k] for k in ('client_name', 'setter_name')}
                )
    return start, end, grouped


COUNTS = tuple(METRICS) + (
    'upcoming',
    'pending_results',
    'unqualified',
    'attendance_credits',
    'attendance_unpriced',
    'sale_credits',
    'sale_unpriced',
)
DEFINITION = (
    'Période au Québec selon le début des visites ; appels et non-qualifiés selon leur enregistrement. '
    'Les appels sont les commandes Orvia dont le poste a décroché, sans présumer de la réponse du prospect ; CDR hors Orvia et résultats manuels exclus. '
    'Client unique actif pour les appels. Les occurrences tenues et les ventes sont affichées séparément des crédits : '
    'une seule visite tenue et une seule prime de vente par processus prospect/client, choisies parmi les premiers résultats valides de tout l’historique, puis filtrées sur cette période. '
    'Tarifs CAD figés lors de la valorisation. Les corrections de présence/vente recalculent l’éligibilité sans effacer les anciens tarifs ni exécuter de paiement. '
    'Un tarif non défini reste à valoriser ; les montants connus sont incomplets dans ce cas. Les non-qualifiés ne génèrent aucun crédit.'
)


def report(request):
    from .isolation_compensation_calls import load

    start, end, grouped = build(request.query_params)
    try:
        calls = load(request.user.pk, start, end)
    except Exception:
        # An optional source failure must never become an invented zero or hide the financial report.
        calls = None
    if calls is not None:
        client = calls['client']
        for row in calls['results']:
            key = (client['id'] if client else None, row['user_id'])
            target = grouped.setdefault(
                key,
                {
                    'client_id': key[0],
                    'client_name': client['name'] if client else 'Client non défini',
                    'setter_id': key[1],
                    'setter_name': row['user__username'],
                },
            )
            target.update({field: row[field] for field in ('calls', 'attempts', 'uncertain')})
    if len(grouped) > 5000:
        raise ValidationError('Rapport limité à 5 000 groupes.')
    rows = []
    for key in sorted(grouped, key=lambda key: (key[0] or 0, key[1])):
        row = grouped[key]
        for field in COUNTS:
            row.setdefault(field, 0)
        for field in ('calls', 'attempts', 'uncertain'):
            row.setdefault(field, 0 if calls is not None else None)
        for field in ('attendance_amount', 'sale_amount'):
            row[field] = money(row.get(field) or Decimal('0'))
        row['amount_cad'] = money(Decimal(row['attendance_amount']) + Decimal(row['sale_amount']))
        row.setdefault('rate_attendance_cad', None)
        row.setdefault('rate_sale_bonus_cad', None)
        row.setdefault('rate_revision', 0)
        row['complete'] = not (
            row['attendance_unpriced'] or row['sale_unpriced'] or row['pending_results']
        )
        row['presence_rate'] = (
            round(100 * row['attended'] / (row['attended'] + row['absent']), 2)
            if row['attended'] + row['absent']
            else None
        )
        row['closing_rate'] = (
            round(100 * row['sales'] / row['attended'], 2) if row['attended'] else None
        )
        rows.append(row)
    totals = {field: sum(row[field] for row in rows) for field in COUNTS}
    for field in ('attendance_amount', 'sale_amount', 'amount_cad'):
        totals[field] = money(sum((Decimal(row[field]) for row in rows), Decimal('0')))
    totals['complete'] = all(row['complete'] for row in rows)
    for field in ('calls', 'attempts', 'uncertain'):
        totals[field] = sum(row[field] for row in rows) if calls is not None else None
    totals['presence_rate'] = (
        round(100 * totals['attended'] / (totals['attended'] + totals['absent']), 2)
        if totals['attended'] + totals['absent']
        else None
    )
    totals['closing_rate'] = (
        round(100 * totals['sales'] / totals['attended'], 2) if totals['attended'] else None
    )
    return {
        'from': start,
        'to': end,
        'timezone': 'America/Toronto',
        'currency': 'CAD',
        'as_of': timezone.now(),
        'totals': totals,
        'calls_available': calls is not None,
        'definition': DEFINITION,
    }, rows


@api_view(['GET'])
@authentication_classes([WorkAuthentication])
@permission_classes([IsAuthenticated])
def summary(request):
    admin(request)
    result, rows = report(request)
    kind = request.query_params.get('export', '')
    if kind:
        if kind not in ('csv', 'xlsx'):
            raise ValidationError('Export CSV ou XLSX requis.')
        from .isolation_compensation_export import export

        response = export(result, rows, kind)
        AuditEvent.objects.create(
            action='isolation.compensation.exported',
            metadata={
                'actor_portal_id': request.user.pk,
                'from': str(result['from']),
                'to': str(result['to']),
                'format': kind,
                'calls_available': result['calls_available'],
            },
        )
    else:
        pager = Pager()
        selected = pager.paginate_queryset(rows, request)
        result['groups'] = {
            'count': len(rows),
            'next': pager.get_next_link(),
            'previous': pager.get_previous_link(),
            'results': selected,
        }
        response = Response(result)
    response['Cache-Control'] = 'no-store'
    return response
