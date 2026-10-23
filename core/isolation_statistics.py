"""Scoped visit-start cohorts with local weeks and explicit presence/sale denominators."""

from datetime import datetime, time, timedelta, timezone as utc
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.db.models import Count, Q, Subquery, OuterRef
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from .isolation_work import WorkAuthentication
from .models import IsolationVisit, AuditEvent
from .isolation_statistics_export import response as export_response
from packages.stats_series import daily, previous


class StatisticsAuthentication(WorkAuthentication):
    roles = ('administrator', 'client', 'setter', 'closer')


def period(params, now):
    name = params.get('timezone', 'UTC')
    try:
        zone = ZoneInfo(name)
    except (ValueError, ZoneInfoNotFoundError):
        raise ValidationError('Fuseau IANA invalide.')
    today = now.astimezone(zone).date()
    try:
        if params.get('week_of'):
            if 'from' in params or 'to' in params:
                raise ValueError()
            selected = parse_date(params['week_of'])
            if selected is None:
                raise ValueError()
            start = selected - timedelta(days=selected.weekday())
            end = start + timedelta(days=6)
        else:
            start = parse_date(params.get('from', (today - timedelta(days=29)).isoformat()))
            end = parse_date(params.get('to', today.isoformat()))
        if start is None or end is None or end < start or (end - start).days > 365:
            raise ValueError()
        exclusive = end + timedelta(days=1)
        lower = datetime.combine(start, time.min, zone).astimezone(utc.utc)
        upper = datetime.combine(exclusive, time.min, zone).astimezone(utc.utc)
    except (ValueError, OverflowError):
        raise ValidationError(
            'Période AAAA-MM-JJ valide de 366 jours maximum ; semaine et dates personnalisées sont exclusives.'
        )
    return start, end, lower, upper, name


def metrics(now):
    return {
        'visits': Count('pk', distinct=True),
        'prospects': Count('prospect_id', distinct=True),
        'cancelled': Count('pk', filter=Q(status='cancelled'), distinct=True),
        'upcoming': Count('pk', filter=Q(status='scheduled', starts_at__gt=now), distinct=True),
        'reported': Count('pk', filter=Q(result__isnull=False), distinct=True),
        'performed': Count('pk', filter=Q(result__performed=True), distinct=True),
        'not_performed': Count('pk', filter=Q(result__performed=False), distinct=True),
        'closed': Count('pk', filter=Q(result__performed=True, result__closed=True), distinct=True),
        'not_closed': Count(
            'pk', filter=Q(result__performed=True, result__closed=False), distinct=True
        ),
        'closure_unknown': Count(
            'pk', filter=Q(result__performed=True, result__closed__isnull=True), distinct=True
        ),
        'unassigned_closer': Count('pk', filter=Q(closer_id__isnull=True), distinct=True),
        'results_due': Count(
            'pk', filter=Q(status='scheduled', ends_at__lte=now, result__isnull=True), distinct=True
        ),
        'interested': Count('pk', filter=Q(result__outcome='interested'), distinct=True),
        'not_interested': Count('pk', filter=Q(result__outcome='not_interested'), distinct=True),
        'follow_up': Count('pk', filter=Q(result__outcome='follow_up'), distinct=True),
    }


def finish(row):
    row['performed_rate'] = (
        round(100 * row['performed'] / row['reported'], 2) if row['reported'] else None
    )
    row['interest_rate'] = (
        round(100 * row['interested'] / row['performed'], 2) if row['performed'] else None
    )
    row['closing_rate'] = (
        round(100 * row['closed'] / row['performed'], 2) if row['performed'] else None
    )
    return row


@api_view(['GET'])
@authentication_classes([StatisticsAuthentication])
@permission_classes([IsAuthenticated])
def statistics(request):
    now = timezone.now()
    kind = request.query_params.get('export', '')
    if kind not in ('', 'csv', 'xlsx'):
        raise ValidationError('Export CSV ou XLSX uniquement')
    start, end, lower, upper, zone = period(request.query_params, now)
    group = request.query_params.get('group', 'setter')
    if group not in ('setter', 'closer'):
        raise ValidationError('Regroupement setter ou closer requis.')

    def scoped(first, last):
        rows = IsolationVisit.objects.filter(starts_at__gte=first, starts_at__lt=last)
        if request.user.role == 'client':
            rows = rows.filter(client_id=request.user.pk)
        if request.user.role == 'setter':
            rows = rows.filter(
                setter_id=request.user.pk, prospect__assigned_setter_id=request.user.pk
            )
        if request.user.role == 'closer':
            rows = rows.filter(closer_id=request.user.pk)
        return rows

    qs = scoped(lower, upper)
    result = {
        'from': start,
        'to': end,
        'timezone': zone,
        'group': group,
        'as_of': now,
        'totals': finish(qs.aggregate(**metrics(now))),
        'definition': f'Période selon le début actuel de la visite, jours inclus dans le fuseau {zone}. Setter d’origine ; closer actuellement affecté. Une réattribution déplace donc les visites et leurs résultats courants dans le groupe du nouveau closer, sans modifier leur auteur historique. Client : ses visites uniquement. Setter : ses réservations dont il conserve le prospect. Closer : ses visites actuellement attribuées. Taux effectué (présence) = tenues / résultats de tenue renseignés. Taux de conclusion observé = ventes explicitement conclues / visites tenues, y compris celles dont la vente reste non renseignée ; ces inconnues sont affichées séparément, pas classées comme ventes perdues. Les annulations, rendez-vous futurs et résultats manquants ne deviennent pas des absences. Prospects distincts par groupe, non additionnables. Un report peut déplacer une visite de période.',
    }
    if not kind:
        # Dashboard only: same-length previous period for trends, and one point per local day.
        local = ZoneInfo(zone)
        try:
            first, last = previous(start, end)
            result['previous'] = {
                'from': first,
                'to': last,
                'totals': finish(
                    scoped(
                        datetime.combine(first, time.min, local).astimezone(utc.utc),
                        lower,
                    ).aggregate(**metrics(now))
                ),
            }
        except OverflowError:
            result['previous'] = None
        result['daily'] = daily(
            qs,
            start,
            end,
            local,
            visits=Count('pk', distinct=True),
            performed=Count('pk', filter=Q(result__performed=True), distinct=True),
            closed=Count(
                'pk', filter=Q(result__performed=True, result__closed=True), distinct=True
            ),
        )
    exported_groups = []
    if request.user.role in ('administrator', 'client'):
        identity = f'{group}_id'
        name = f'{group}_name'
        names = (
            qs.filter(**{identity: OuterRef(identity)})
            .order_by('-created_at', '-pk')
            .values(name)[:1]
        )
        groups = (
            qs.order_by()
            .values(identity)
            .annotate(**metrics(now), **{name: Subquery(names)})
            .order_by(identity)
        )

        def normalize(row):
            if group == 'closer' and row['closer_id'] is None:
                row['closer_name'] = 'Non attribué'
            return finish(row)

        if kind:
            if groups.count() > 5000:
                raise ValidationError('Export limité à 5 000 groupes ; réduisez la période')
            exported_groups = [normalize(row) for row in groups]
        else:
            pager = PageNumberPagination()
            pager.page_size = 25
            rows = pager.paginate_queryset(groups, request)
            result[group + 's'] = {
                'count': pager.page.paginator.count,
                'next': pager.get_next_link(),
                'previous': pager.get_previous_link(),
                'results': [normalize(row) for row in rows],
            }
    if kind:
        response = export_response(result, exported_groups, kind)
        AuditEvent.objects.create(
            action='isolation.statistics.exported',
            metadata={
                'actor_portal_id': request.user.pk,
                'scope': request.user.role,
                'from': str(start),
                'to': str(end),
                'timezone': zone,
                'group': group,
                'format': kind,
            },
        )
        return response
    response = Response(result)
    response['Cache-Control'] = 'no-store'
    return response
