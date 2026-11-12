from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from packages.quebec_period import ZONE, period
from .phone_calls import caller_access
from .models import Membership, PhoneCallAttempt


@api_view(['GET'])
def statistics(request, workspace):
    if workspace not in ('assurance', 'isolation'):
        raise PermissionDenied('Espace invalide.')
    member = caller_access(request.user, workspace)
    start, end, lower, upper = period(request.query_params)
    if request.query_params.get('team') == '1':
        if member.role != 'administrator':
            raise PermissionDenied('Rapport équipe réservé aux administrateurs.')
        rows = PhoneCallAttempt.objects.filter(
            workspace=workspace, created_at__gte=lower, created_at__lt=upper
        )
        metrics = {
            'calls': Count('pk', filter=Q(state='accepted')),
            'attempts': Count('pk', filter=Q(state__in=['accepted', 'rejected', 'unknown'])),
            'uncertain': Count('pk', filter=Q(state='unknown')),
            'calls_over_minute': Count(
                'pk', filter=Q(journal_status='matched', journal_duration__gt=60)
            ),
            'duration_total_seconds': Sum(
                'journal_duration',
                filter=Q(journal_status='matched', journal_duration__isnull=False),
            ),
            'duration_average_seconds': Avg(
                'journal_duration',
                filter=Q(journal_status='matched', journal_duration__isnull=False),
            ),
        }
        return Response(
            {
                'from': start,
                'to': end,
                'timezone': 'America/Toronto',
                'team': list(
                    rows.values('user_id', 'user__username').annotate(**metrics).order_by('user_id')
                ),
            },
            headers={'Cache-Control': 'no-store'},
        )
    agent = request.user.pk
    if request.query_params.get('setter_id'):
        try:
            agent = int(request.query_params['setter_id'])
            if not 1 <= agent <= 9223372036854775807:
                raise ValueError()
        except (ValueError, TypeError):
            raise ValidationError('Setter invalide.') from None
    if member.role != 'administrator' and agent != request.user.pk:
        raise PermissionDenied('Vos appels uniquement.')
    if not Membership.objects.filter(
        user_id=agent,
        workspace=workspace,
        role__in=('setter', 'administrator'),
        active=True,
        user__is_active=True,
    ).exists():
        raise ValidationError('Compte actif de cet espace requis.')
    rows = PhoneCallAttempt.objects.filter(
        workspace=workspace, user_id=agent, created_at__gte=lower, created_at__lt=upper
    )
    metrics = {
        'calls': Count('pk', filter=Q(state='accepted')),
        'attempts': Count('pk', filter=Q(state__in=['accepted', 'rejected', 'unknown'])),
        'uncertain': Count('pk', filter=Q(state='unknown')),
        'calls_over_minute': Count(
            'pk', filter=Q(journal_status='matched', journal_duration__gt=60)
        ),
        'duration_total_seconds': Sum(
            'journal_duration',
            filter=Q(journal_status='matched', journal_duration__isnull=False),
        ),
        'duration_average_seconds': Avg(
            'journal_duration',
            filter=Q(journal_status='matched', journal_duration__isnull=False),
        ),
    }
    daily = list(
        rows.order_by()
        .annotate(day=TruncDate('created_at', tzinfo=ZONE))
        .values('day')
        .annotate(**metrics)
    )
    result = Response(
        {
            'agent_id': agent,
            'from': start,
            'to': end,
            'timezone': 'America/Toronto',
            'totals': {**rows.aggregate(**metrics), 'reached': None},
            'daily': daily,
            'definition': 'Appels acceptés : le poste NEWT a décroché et la composition démarre. La réponse du prospect ne peut pas être déduite. Appels hors Orvia exclus ; états incertains séparés.',
        }
    )
    result['Cache-Control'] = 'no-store'
    return result
