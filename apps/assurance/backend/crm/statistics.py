"""Operational counts over an appointment-start cohort, with explicit denominators."""

from datetime import datetime, time, timedelta
from django.db.models import Count, Q, Subquery, OuterRef
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from .models import Appointment, BusinessAudit
from .statistics_export import response as export_response
from packages.stats_series import daily, previous
from packages.quebec_period import ZONE


def metrics(now):
    return {
        'appointments': Count('pk', distinct=True),
        'cancelled': Count('pk', filter=Q(status='cancelled'), distinct=True),
        'upcoming': Count('pk', filter=Q(status='scheduled', ends_at__gt=now), distinct=True),
        'reported': Count('pk', filter=Q(report__isnull=False), distinct=True),
        'performed': Count('pk', filter=Q(report__performed=True), distinct=True),
        'not_performed': Count('pk', filter=Q(report__performed=False), distinct=True),
        'absent': Count(
            'pk', filter=Q(report__performed=False, report__outcome='absent'), distinct=True
        ),
        'other_not_performed': Count(
            'pk', filter=Q(report__performed=False) & ~Q(report__outcome='absent'), distinct=True
        ),
        'reports_due': Count(
            'pk', filter=Q(status='scheduled', ends_at__lte=now, report__isnull=True), distinct=True
        ),
        'problem_reports': Count('pk', filter=Q(report__problem=True), distinct=True),
        'incidents': Count('incidents', distinct=True),
        'open_tasks': Count(
            'follow_up', filter=Q(follow_up__closed_at__isnull=True), distinct=True
        ),
        'overdue_tasks': Count(
            'follow_up',
            filter=Q(follow_up__closed_at__isnull=True, follow_up__due_at__lt=now),
            distinct=True,
        ),
        'closed_tasks': Count(
            'follow_up', filter=Q(follow_up__closed_at__isnull=False), distinct=True
        ),
    }


def finish(values):
    values['performed_rate'] = (
        round(100 * values['performed'] / values['reported'], 2) if values['reported'] else None
    )
    return values


@api_view(['GET'])
def statistics(request):
    if request.user.role not in ('administrator', 'setter'):
        raise PermissionDenied('Statistiques internes Assurance uniquement')
    kind = request.query_params.get('export', '')
    if kind not in ('', 'csv', 'xlsx'):
        raise ValidationError('Export CSV ou XLSX uniquement')
    today = timezone.now().astimezone(ZONE).date()
    try:
        start = parse_date(
            request.query_params.get('from', (today - timedelta(days=29)).isoformat())
        )
        end = parse_date(request.query_params.get('to', today.isoformat()))
    except ValueError:
        raise ValidationError('Dates au format AAAA-MM-JJ requises')
    if start is None or end is None or end < start or (end - start).days > 365:
        raise ValidationError('Période valide de 366 jours maximum requise')
    try:
        exclusive = end + timedelta(days=1)
    except OverflowError:
        raise ValidationError('Date de fin hors limites')
    now = timezone.now()

    def scoped(first, upper):
        rows = Appointment.objects.filter(
            starts_at__gte=datetime.combine(first, time.min, ZONE),
            starts_at__lt=datetime.combine(upper, time.min, ZONE),
        )
        return rows.filter(setter_id=request.user.pk) if request.user.role == 'setter' else rows

    qs = scoped(start, exclusive)
    totals = finish(qs.aggregate(**metrics(now)))
    result = {
        'from': start,
        'to': end,
        'timezone': 'America/Toronto',
        'as_of': now,
        'totals': totals,
        'definition': 'Période selon le début actuel du rendez-vous (heure du Québec). Attribution statistique au setter d’origine du rendez-vous, même si le suivi est réattribué. Tâches selon leur état actuel. Taux effectué = Oui / comptes rendus renseignés ; absence de compte rendu exclue. Absences uniquement selon la déclaration explicite du conseiller ; les anciens Non restent des non-effectués sans absence présumée.',
    }
    if not kind:
        # Dashboard only: same-length previous period for trends, and one point per day.
        try:
            before = previous(start, end)
            result['previous'] = {
                'from': before[0],
                'to': before[1],
                'totals': finish(scoped(before[0], start).aggregate(**metrics(now))),
            }
        except OverflowError:
            result['previous'] = None
        result['daily'] = daily(
            qs,
            start,
            end,
            ZONE,
            appointments=Count('pk', distinct=True),
            performed=Count('pk', filter=Q(report__performed=True), distinct=True),
            cancelled=Count('pk', filter=Q(status='cancelled'), distinct=True),
        )
    groups = []
    if request.user.role == 'administrator':
        names = (
            Appointment.objects.filter(setter_id=OuterRef('setter_id'))
            .order_by('-created_at', '-pk')
            .values('setter_name')[:1]
        )
        grouped = (
            qs.order_by()
            .values('setter_id')
            .annotate(**metrics(now), setter_name=Subquery(names))
            .order_by('setter_id')
        )
        if kind:
            if grouped.count() > 5000:
                raise ValidationError('Export limité à 5 000 setters. Réduisez la période.')
            groups = [finish(row) for row in grouped]
        if not kind:
            pager = PageNumberPagination()
            pager.page_size = 25
            page = pager.paginate_queryset(grouped, request)
            result['setters'] = {
                'count': pager.page.paginator.count,
                'next': pager.get_next_link(),
                'previous': pager.get_previous_link(),
                'results': [finish(row) for row in page],
            }
    if kind:
        BusinessAudit.objects.create(
            actor_id=request.user.pk,
            object_id=0,
            action='statistics.exported',
            metadata={
                'from': str(start),
                'to': str(end),
                'format': kind,
                'scope': request.user.role,
            },
        )
        return export_response(result, groups, kind)
    return Response(result)
