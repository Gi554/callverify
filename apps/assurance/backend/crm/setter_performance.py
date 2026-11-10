from rest_framework.decorators import api_view
from packages.setter_performance import performance
from .admin_alerts import Store as AlertStore
from .models import ContactCallOutcome


class Store(AlertStore):
    snapshot = 'qualification_snapshot'

    @staticmethod
    def outcomes(agent, lower, upper):
        return ContactCallOutcome.objects.filter(
            setter_id=agent, created_at__gte=lower, created_at__lt=upper
        )


@api_view(['GET'])
def own(request, agent=None):
    return performance(Store, request, agent)
