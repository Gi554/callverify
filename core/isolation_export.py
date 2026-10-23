"""Isolation prospect export (CSV or Excel) over exactly the work queue's scope and filters."""

from rest_framework.decorators import action
from packages.exports import kind, bounded, response
from .models import AuditEvent
from .isolation_activity import STATUSES


class ExportMixin:
    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        file = kind(request)
        rows = bounded(self.get_queryset(), file)
        headers = [
            'Réf. fiche',
            'Référence',
            'Nom',
            'Téléphone saisi',
            'Numéro normalisé',
            'Campagne',
            'Setter',
            'Statut commercial',
            'Rappel prévu',
        ]
        values = [
            [
                row.pk,
                row.reference,
                row.name,
                row.raw_phone,
                row.phone.e164 if row.phone_id else '',
                row.campaign.name,
                row.assigned_setter_name or 'Non affecté',
                STATUSES.get(row.commercial_status, row.commercial_status),
                row.callback_at,
            ]
            for row in rows
        ]
        AuditEvent.objects.create(
            action='isolation.prospects.exported',
            metadata={
                'actor_portal_id': request.user.pk,
                'file': file,
                'rows': len(rows),
                'filters': {
                    key: request.query_params.get(key, '')[:250]
                    for key in ('search', 'owner', 'commercial_status', 'due', 'queue')
                },
            },
        )
        return response(file, headers, values, 'prospects-isolation', 'Prospects')
