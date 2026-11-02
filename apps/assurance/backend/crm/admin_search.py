from rest_framework.decorators import api_view
from packages.admin_search import search
from .admin_alerts import Store as AlertStore
from . import models


class Store(AlertStore):
    workspace = 'assurance'
    contact_status = 'status'
    campaign_id = 'import_batch_id'
    campaign_name = 'import_batch__filename'
    target_label = 'Conseiller du rendez-vous'

    @staticmethod
    def contact_labels():
        from .pipeline import pipeline

        return {s['key']: s['label'] for s in pipeline().stages}

    @staticmethod
    def export_audit(actor, file, count, filters):
        models.BusinessAudit.objects.create(
            actor_id=actor,
            object_id=0,
            action='admin_search.exported',
            metadata={'file': file, 'rows': count, 'filters': filters},
        )


@api_view(['GET'])
def results(request):
    return search(Store, request)
