"""Isolation prospect export (CSV or Excel) over exactly the work queue's scope and filters."""

from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from django.db.models import OuterRef, Subquery
from django.db.models.fields.json import KeyTextTransform
from packages.exports import kind, bounded, response
from .models import AuditEvent, ProspectActivity
from .isolation_activity import STATUSES
from .isolation_followups import RESULTS


def with_latest_call_result(queryset):
    latest = (
        ProspectActivity.objects.filter(prospect_id=OuterRef('pk'), kind='call_result')
        .order_by('-created_at', '-pk')
        .annotate(result=KeyTextTransform('result', 'changes'))
    )
    return queryset.annotate(last_call_result=Subquery(latest.values('result')[:1]))


class ExportMixin:
    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        if request.user.role == 'setter':
            raise PermissionDenied(
                'Les exports sont réservés au client, conseiller ou administrateur.'
            )
        file = kind(request)
        rows = bounded(with_latest_call_result(self.get_queryset()), file)
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
            'Dernier résultat d’appel',
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
                RESULTS.get(row.last_call_result, row.last_call_result or ''),
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
                    for key in (
                        'search',
                        'owner',
                        'commercial_status',
                        'call_result',
                        'due',
                        'queue',
                    )
                },
            },
        )
        return response(file, headers, values, 'prospects-isolation', 'Prospects')
