"""Server-persisted Isolation call-session cursor."""

from django.db import transaction
from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
from zoneinfo import ZoneInfo
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError, APIException
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .isolation_phone_calls import destination
from .isolation_work import visible
from .isolation_work import WorkAuthentication
from .models import (
    CallSessionProgress,
    IsolationClientFollowUp,
    IsolationUnqualified,
    IsolationVisit,
    IsolationVisitResult,
    ProspectActivity,
)


class Conflict(APIException):
    status_code = 409
    default_detail = 'La progression de session a changé. Rechargez la session.'
    default_code = 'call_session_conflict'


def state(row):
    return {
        'active': row.active,
        'visited_ids': row.visited_prospect_ids,
        'current_id': row.current_prospect_id,
        'updated_at': row.updated_at,
    }


@api_view(['GET', 'POST'])
@authentication_classes([WorkAuthentication])
@permission_classes([IsAuthenticated])
def call_session(request):
    if request.user.role not in ('setter', 'administrator'):
        raise PermissionDenied('Session d’appels réservée aux setters et administrateurs.')
    row, _ = CallSessionProgress.objects.get_or_create(portal_user_id=request.user.pk)
    if request.method == 'GET':
        return Response(state(row))

    data = request.data
    if not isinstance(data, dict) or set(data) - {'action', 'prospect_id'}:
        raise ValidationError('Champs de progression invalides.')
    action = data.get('action')
    if action not in ('start', 'begin', 'complete', 'finish'):
        raise ValidationError('Action de session invalide.')

    with transaction.atomic():
        row = CallSessionProgress.objects.select_for_update().get(pk=row.pk)
        if action == 'start':
            row.active = True
            row.visited_prospect_ids = []
            row.current_prospect_id = None
        elif action == 'begin':
            try:
                prospect_id = int(data.get('prospect_id'))
            except (TypeError, ValueError):
                raise ValidationError('Prospect de session invalide.')
            if not row.active:
                raise Conflict('La session n’est pas active.')
            if row.current_prospect_id is not None:
                raise Conflict('Une fiche est déjà en cours. Reprenez-la avant de continuer.')
            if prospect_id in row.visited_prospect_ids:
                raise Conflict('Cette fiche est déjà terminée dans la session.')
            prospect = (
                visible(request.user)
                .filter(assigned_setter_id=request.user.pk, pk=prospect_id)
                .first()
            )
            if prospect is None:
                raise ValidationError('Cette fiche n’est plus dans votre lot.')
            destination(prospect)
            # Mirror the active prospecting queue checks so a stale browser cannot
            # start a call after a booking, decline, attendance, or open follow-up.
            latest = (
                ProspectActivity.objects.filter(prospect_id=prospect_id, kind='call_result')
                .order_by('-created_at', '-pk')
                .first()
            )
            retryable = latest is not None and latest.changes.get('result') in (
                'voicemail',
                'unreachable',
            )
            retry_total = ProspectActivity.objects.filter(
                prospect_id=prospect_id,
                kind='call_result',
                changes__result__in=('voicemail', 'unreachable'),
            ).count()
            now = timezone.now()
            quebec_now = now.astimezone(ZoneInfo('America/Toronto'))
            day_start = quebec_now.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            retry_today = ProspectActivity.objects.filter(
                prospect_id=prospect_id,
                kind='call_result',
                changes__result__in=('voicemail', 'unreachable'),
                created_at__gte=day_start,
                created_at__lt=day_end,
            ).count()
            blocked = (
                prospect.commercial_status == 'not_interested'
                or ProspectActivity.objects.filter(
                    prospect_id=prospect_id,
                    kind='call_result',
                    changes__result='not_interested',
                ).exists()
                or IsolationVisitResult.objects.filter(
                    visit__prospect_id=prospect_id, performed=True
                ).exists()
                or IsolationVisit.objects.filter(prospect_id=prospect_id, status='scheduled')
                .filter(
                    Q(result__isnull=True)
                    | Q(result__performed=True)
                    | ~Q(result__outcome='unqualified')
                )
                .exists()
                or IsolationUnqualified.objects.filter(
                    prospect_id=prospect_id, active=True
                ).exists()
                or IsolationClientFollowUp.objects.filter(
                    visit__prospect_id=prospect_id, closed_at__isnull=True
                ).exists()
                or (latest is not None and latest.changes.get('result') and not retryable)
                or (retryable and (retry_total >= 6 or retry_today >= 2))
            )
            if blocked:
                raise ValidationError('Cette fiche n’est plus admissible dans la session.')
            row.current_prospect_id = prospect_id
        elif action == 'complete':
            try:
                prospect_id = int(data.get('prospect_id'))
            except (TypeError, ValueError):
                raise ValidationError('Prospect de session invalide.')
            if prospect_id in row.visited_prospect_ids and row.current_prospect_id is None:
                return Response(state(row))
            if row.current_prospect_id != prospect_id:
                raise Conflict('La fiche terminée ne correspond pas à la fiche en cours.')
            row.visited_prospect_ids = list(dict.fromkeys([*row.visited_prospect_ids, prospect_id]))
            row.current_prospect_id = None
        else:  # finish
            row.active = False
            row.current_prospect_id = None
            row.visited_prospect_ids = []
        row.save()
    return Response(state(row))
