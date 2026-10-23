"""Prospect export (CSV or Excel) over exactly the list's visibility and filters."""

from rest_framework.decorators import action
from packages.exports import kind, bounded, response
from .custom_fields import schema
from .models import BusinessAudit
from .pipeline import pipeline


class ContactExportMixin:
    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        file = kind(request)
        rows = bounded(self.get_queryset(), file)
        labels = {stage['key']: stage['label'] for stage in pipeline().stages}
        # Advisors only receive the fields the administration made visible to them.
        fields = [
            field
            for field in schema().fields
            if field.get('active', True)
            and (request.user.role != 'advisor' or field.get('advisor_visible'))
        ]
        headers = ['Réf. fiche', 'Nom', 'Téléphone', 'E-mail', 'Étape', 'Mis à jour le']
        headers += [field['label'] for field in fields]
        values = [
            [
                row.pk,
                row.name,
                row.phone,
                row.email,
                labels.get(row.status, row.status),
                row.updated_at,
            ]
            + [(row.custom_values or {}).get(field['key']) for field in fields]
            for row in rows
        ]
        BusinessAudit.objects.create(
            actor_id=request.user.pk,
            object_id=0,
            action='contacts.exported',
            metadata={
                'file': file,
                'rows': len(rows),
                'search': request.query_params.get('search', '')[:250],
                'status': request.query_params.get('status', '')[:40],
            },
        )
        return response(file, headers, values, 'prospects-assurance', 'Prospects')
