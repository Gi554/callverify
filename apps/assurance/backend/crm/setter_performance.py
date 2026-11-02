from rest_framework.decorators import api_view
from packages.setter_performance import performance
from .admin_alerts import Store as AlertStore


class Store(AlertStore):
    snapshot = 'qualification_snapshot'


@api_view(['GET'])
def own(request, agent=None):
    return performance(Store, request, agent)
