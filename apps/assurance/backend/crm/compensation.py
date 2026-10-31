"""Attendance-based CAD accruals; immutable unit prices, no payment execution."""

from decimal import Decimal
from django.db import transaction
from django.db.models import Count, Q, Sum, F, OuterRef, Subquery
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from packages.quebec_period import period
from .models import Appointment, AppointmentReport, AdvisorAssignment, SetterRate, BusinessAudit
from .leases import Conflict


def administrator(request):
    if request.user.role != 'administrator':
        raise PermissionDenied('Rémunération réservée à l’administration Assurance.')


def capture(report, appointment, actor_id):
    if not report.performed or report.unit_rate_cad is not None:
        return False
    rate = SetterRate.objects.filter(pk=appointment.setter_id, amount__isnull=False).first()
    if not rate:
        return False
    changed = AppointmentReport.objects.filter(pk=report.pk, unit_rate_cad__isnull=True).update(
        unit_rate_cad=rate.amount, rate_revision=rate.revision, valued_at=timezone.now()
    )
    if changed:
        BusinessAudit.objects.create(
            actor_id=actor_id,
            object_id=appointment.pk,
            action='compensation.rate_captured',
            metadata={
                'setter_id': appointment.setter_id,
                'unit_rate_cad': str(rate.amount),
                'rate_revision': rate.revision,
            },
        )
    return bool(changed)


def roster():
    names = {}
    for model in (AdvisorAssignment, Appointment):
        latest = (
            model.objects.filter(setter_id=OuterRef('setter_id'))
            .order_by('-pk')
            .values('setter_name')[:1]
        )
        names.update(
            dict(
                model.objects.values('setter_id')
                .distinct()
                .annotate(latest_name=Subquery(latest))
                .values_list('setter_id', 'latest_name')
            )
        )
    return names


def money(value):
    return format(value or Decimal('0'), '.2f')


def scoped(params):
    start, end, lower, upper = period(params)
    return start, end, Appointment.objects.filter(starts_at__gte=lower, starts_at__lt=upper)


@api_view(['GET'])
def summary(request):
    administrator(request)
    start, end, appointments = scoped(request.query_params)
    now = timezone.now()
    eligible = Q(status='scheduled', report__performed=True)
    metrics = dict(
        booked=Count('pk'),
        transmitted=Count('pk', filter=Q(calendar='external_link')),
        upcoming=Count('pk', filter=Q(status='scheduled', starts_at__gt=now, report__isnull=True)),
        attended=Count('pk', filter=eligible),
        absent=Count(
            'pk', filter=Q(status='scheduled', report__performed=False, report__outcome='absent')
        ),
        payable=Count('pk', filter=eligible),
        unpriced=Count('pk', filter=eligible & Q(report__unit_rate_cad__isnull=True)),
        amount_cad=Sum('report__unit_rate_cad', filter=eligible),
    )
    groups = {r['setter_id']: r for r in appointments.values('setter_id').annotate(**metrics)}
    rates = {r.setter_id: r for r in SetterRate.objects.all()}
    rows = []
    for pk, name in sorted(roster().items()):
        row = groups.get(pk, {key: 0 for key in metrics})
        rate = rates.get(pk)
        rows.append(
            {
                **row,
                'setter_id': pk,
                'setter_name': name,
                'amount_cad': money(row['amount_cad']),
                'rate_cad': str(rate.amount) if rate and rate.amount is not None else None,
                'rate_revision': rate.revision if rate else 0,
            }
        )
    totals = appointments.aggregate(**metrics)
    totals['amount_cad'] = money(totals['amount_cad'])
    pager = PageNumberPagination()
    pager.page_size = 25
    page = pager.paginate_queryset(rows, request)
    response = pager.get_paginated_response(page)
    response.data.update(
        {
            'from': start,
            'to': end,
            'timezone': 'America/Toronto',
            'currency': 'CAD',
            'totals': totals,
            'as_of': now,
            'definition': 'Rendez-vous selon leur date de début au Québec ; pris = occurrences enregistrées, transmis = nouveau formulaire externe. Les réservations non transmises sont inconnues du CRM. Rémunération = présences confirmées, hors annulations. Montant calculé au tarif conservé lors de la validation ou de la valorisation ; les présences sans tarif restent à valoriser. Aucun paiement exécuté.',
        }
    )
    response['Cache-Control'] = 'no-store'
    return response


class RateInput(serializers.Serializer):
    amount_cad = serializers.DecimalField(
        max_digits=9, decimal_places=2, min_value=Decimal('0'), allow_null=True
    )
    revision = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(max_length=1000)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés.')
        return data


@api_view(['POST'])
def rate(request, setter_id):
    administrator(request)
    if setter_id not in roster():
        raise ValidationError('Setter Assurance connu requis (affectation ou rendez-vous).')
    serializer = RateInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    with transaction.atomic():
        SetterRate.objects.get_or_create(setter_id=setter_id)
        row = SetterRate.objects.select_for_update().get(pk=setter_id)
        before = row.amount
        if not SetterRate.objects.filter(pk=setter_id, revision=data['revision']).update(
            amount=data['amount_cad'], revision=F('revision') + 1, updated_at=timezone.now()
        ):
            raise Conflict('Tarif modifié : actualisez avant de réessayer.')
        BusinessAudit.objects.create(
            actor_id=request.user.pk,
            object_id=setter_id,
            action='compensation.rate_changed',
            metadata={
                'before': str(before) if before is not None else None,
                'after': str(data['amount_cad']) if data['amount_cad'] is not None else None,
                'revision': data['revision'] + 1,
                'reason': data['reason'],
            },
        )
    return Response({'recorded': True})


class ValueInput(serializers.Serializer):
    starts_on = serializers.DateField(input_formats=['%Y-%m-%d'])
    ends_on = serializers.DateField(input_formats=['%Y-%m-%d'])
    rate_revision = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(max_length=1000)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés.')
        return data


@api_view(['POST'])
def value_missing(request, setter_id):
    administrator(request)
    serializer = ValueInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    start, end, appointments = scoped({'from': str(data['starts_on']), 'to': str(data['ends_on'])})
    with transaction.atomic():
        rate = SetterRate.objects.select_for_update().filter(pk=setter_id).first()
        if not rate or rate.amount is None:
            raise ValidationError('Renseignez d’abord le tarif du setter.')
        if rate.revision != data['rate_revision']:
            raise Conflict('Tarif modifié : actualisez.')
        # Serialize with reports, cancellations and corrections in the same appointment order.
        ids = list(
            appointments.filter(setter_id=setter_id, status='scheduled')
            .order_by('pk')
            .select_for_update()
            .values_list('pk', flat=True)
        )
        reports = AppointmentReport.objects.filter(
            appointment_id__in=ids, performed=True, unit_rate_cad__isnull=True
        )
        count = reports.update(
            unit_rate_cad=rate.amount, rate_revision=rate.revision, valued_at=timezone.now()
        )
        BusinessAudit.objects.create(
            actor_id=request.user.pk,
            object_id=setter_id,
            action='compensation.period_valued',
            metadata={
                'from': str(start),
                'to': str(end),
                'count': count,
                'unit_rate_cad': str(rate.amount),
                'rate_revision': rate.revision,
                'reason': data['reason'],
            },
        )
    return Response({'valued': count})


@api_view(['GET'])
def details(request, setter_id):
    administrator(request)
    start, end, appointments = scoped(request.query_params)
    pager = PageNumberPagination()
    pager.page_size = 25
    rows = pager.paginate_queryset(
        appointments.filter(setter_id=setter_id)
        .select_related('report')
        .order_by('starts_at', 'pk'),
        request,
    )
    output = []
    for row in rows:
        report = getattr(row, 'report', None)
        eligible = row.status == 'scheduled' and report is not None and report.performed
        output.append(
            {
                'id': row.pk,
                'contact_id': row.contact_id,
                'starts_at': row.starts_at,
                'advisor_name': row.advisor_name,
                'status': row.status,
                'performed': report.performed if report else None,
                'payable': eligible,
                'unit_rate_cad': str(report.unit_rate_cad)
                if report and report.unit_rate_cad is not None
                else None,
                'amount_cad': money(report.unit_rate_cad)
                if eligible and report.unit_rate_cad is not None
                else None,
                'rate_revision': report.rate_revision if report else None,
                'valued_at': report.valued_at if report else None,
            }
        )
    response = pager.get_paginated_response(output)
    response['Cache-Control'] = 'no-store'
    return response
