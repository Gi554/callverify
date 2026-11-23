"""Isolation prospect export (CSV or Excel) over exactly the work queue's scope and filters."""

from rest_framework.decorators import action
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from rest_framework.exceptions import PermissionDenied, ValidationError
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
    return queryset.annotate(
        last_call_result=Subquery(latest.values('result')[:1]),
        last_call_result_at=Subquery(latest.values('created_at')[:1]),
    )


def filter_call_result_period(queryset, params):
    raw_start = params.get('call_result_from', '')
    raw_end = params.get('call_result_to', '')
    if not raw_start and not raw_end:
        return queryset
    try:
        start = date.fromisoformat(raw_start) if raw_start else None
        end = date.fromisoformat(raw_end) if raw_end else None
        if (start and start.isoformat() != raw_start) or (end and end.isoformat() != raw_end):
            raise ValueError
        if start and end and start > end:
            raise ValueError
        zone = ZoneInfo('America/Toronto')
        lower = datetime.combine(start, time.min, zone) if start else None
        upper = datetime.combine(end + timedelta(days=1), time.min, zone) if end else None
    except (ValueError, OverflowError):
        raise ValidationError('Période invalide : dates AAAA-MM-JJ, du début à la fin.')
    # Determine the latest result over the entire history BEFORE applying the dates.
    queryset = with_latest_call_result(queryset)
    if lower:
        queryset = queryset.filter(last_call_result_at__gte=lower)
    if upper:
        queryset = queryset.filter(last_call_result_at__lt=upper)
    return queryset


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
                        'call_result_from',
                        'call_result_to',
                        'due',
                        'queue',
                    )
                },
            },
        )
        return response(file, headers, values, 'prospects-isolation', 'Prospects')
