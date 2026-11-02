from rest_framework.decorators import api_view
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from packages.payable_appointments import payable
from .isolation_alerts import Store as AlertStore
from .isolation_work import WorkAuthentication


class Store(AlertStore):
    # Isolation pays attended appointments, counted apart when the sale was concluded.
    split_sales = True


@api_view(['GET'])
@authentication_classes([WorkAuthentication])
@permission_classes([IsAuthenticated])
def appointments(request):
    return payable(Store, request)
