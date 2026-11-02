from rest_framework.decorators import api_view
from packages.admin_search import search
from .isolation_alerts import Store as AlertStore
from .isolation_work import WorkAuthentication
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from . import models


class Store(AlertStore):
    workspace = 'isolation'
    contact_status = 'commercial_status'
    campaign_id = 'campaign_id'
    campaign_name = 'campaign__name'
    target_label = 'Client de la visite'

    @staticmethod
    def contact_labels():
        from .isolation_activity import STATUSES

        return STATUSES

    @staticmethod
    def export_audit(actor, file, count, filters):
        models.AuditEvent.objects.create(
            action='isolation.admin_search.exported',
            metadata={'actor_portal_id': actor, 'file': file, 'rows': count, 'filters': filters},
        )


@api_view(['GET'])
@authentication_classes([WorkAuthentication])
@permission_classes([IsAuthenticated])
def results(request):
    return search(Store, request)
