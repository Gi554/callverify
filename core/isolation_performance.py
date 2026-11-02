from rest_framework.decorators import api_view
from packages.setter_performance import performance
from .isolation_alerts import Store as AlertStore
from .isolation_work import WorkAuthentication
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated


class Store(AlertStore):
    snapshot = 'c2_snapshot'

    @staticmethod
    def money_sources(agent):
        from .isolation_compensation import credited

        return [
            (credited('attendance').filter(setter_id=agent), 'result__attendance_unit_cad'),
            (credited('sale').filter(setter_id=agent), 'result__sale_unit_cad'),
        ]


@api_view(['GET'])
@authentication_classes([WorkAuthentication])
@permission_classes([IsAuthenticated])
def own(request, agent=None):
    return performance(Store, request, agent)
