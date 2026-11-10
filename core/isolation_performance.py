from rest_framework.decorators import api_view
from packages.setter_performance import performance
from .isolation_alerts import Store as AlertStore
from .isolation_work import WorkAuthentication
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.db.models.fields.json import KeyTextTransform
from .models import ProspectActivity


class Store(AlertStore):
    snapshot = 'c2_snapshot'

    @staticmethod
    def outcomes(agent, lower, upper):
        return ProspectActivity.objects.filter(
            author_portal_id=agent,
            kind='call_result',
            created_at__gte=lower,
            created_at__lt=upper,
        ).annotate(result=KeyTextTransform('result', 'changes'))


@api_view(['GET'])
@authentication_classes([WorkAuthentication])
@permission_classes([IsAuthenticated])
def own(request, agent=None):
    return performance(Store, request, agent)
