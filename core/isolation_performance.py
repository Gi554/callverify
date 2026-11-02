from rest_framework.decorators import api_view
from packages.setter_performance import performance
from .isolation_alerts import Store as AlertStore
from .isolation_work import WorkAuthentication
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated


class Store(AlertStore):
    snapshot = 'c2_snapshot'


@api_view(['GET'])
@authentication_classes([WorkAuthentication])
@permission_classes([IsAuthenticated])
def own(request, agent=None):
    return performance(Store, request, agent)
