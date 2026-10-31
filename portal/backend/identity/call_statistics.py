"""Admin aggregate of actual Orvia phone commands, never declared contact outcomes."""

from django.db.models import Count, Q
from rest_framework.decorators import api_view
from rest_framework.response import Response
from packages.quebec_period import period
from .management_api import require_admin
from .models import PhoneCallAttempt


@api_view(['GET'])
def statistics(request):
    require_admin(request.user, 'assurance')
    start, end, lower, upper = period(request.query_params)
    rows = PhoneCallAttempt.objects.filter(
        workspace='assurance', created_at__gte=lower, created_at__lt=upper
    )
    metrics = {
        'calls': Count('pk', filter=Q(state='accepted')),
        'attempts': Count('pk', filter=Q(state__in=['accepted', 'rejected', 'unknown'])),
        'uncertain': Count('pk', filter=Q(state='unknown')),
    }
    response = Response(
        {
            'from': start,
            'to': end,
            'timezone': 'America/Toronto',
            'results': list(
                rows.values('user_id', 'user__username').annotate(**metrics).order_by('user_id')
            ),
            'totals': rows.aggregate(**metrics),
            'definition': 'Appels Orvia dont le poste a décroché (accepted), sans présumer de la réponse du prospect. Les appels composés hors Orvia et les résultats manuels de fiche sont exclus. Les commandes bloquées/en cours ne sont pas des appels effectués ; les réponses incertaines sont comptées séparément.',
        }
    )
    response['Cache-Control'] = 'no-store'
    return response
