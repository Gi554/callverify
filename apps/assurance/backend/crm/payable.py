from rest_framework.decorators import api_view
from packages.payable_appointments import payable
from .admin_alerts import Store as AlertStore


class Store(AlertStore):
    # In Assurance every attended and validated appointment is payable, sale or not.
    split_sales = False


@api_view(['GET'])
def appointments(request):
    return payable(Store, request)
