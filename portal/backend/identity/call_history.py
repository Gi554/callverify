"""Call history: setters read their own call commands, administrators the whole workspace."""

import logging

from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from .models import Membership, PhoneCallAttempt
from .management_api import require_admin
from packages.newt.cdr import fetch_recording
from packages.newt.directory import DirectoryUnavailable
from django.conf import settings

STATES = ('dispatching', 'accepted', 'rejected', 'blocked', 'unknown')
logger = logging.getLogger(__name__)


class Pager(PageNumberPagination):
    page_size = 25


def role_in(user, workspace):
    membership = Membership.objects.filter(
        user=user, workspace=workspace, active=True, role__in=('setter', 'administrator')
    ).first()
    if not user.is_active or membership is None:
        raise PermissionDenied('Historique réservé aux setters et administrateurs de cet espace.')
    return membership.role


def output(row, administrator):
    result = {
        'request_id': str(row.request_id),
        'created_at': row.created_at,
        'updated_at': row.updated_at,
        'state': row.state,
        'contact_id': row.contact_id,
        'contact_label': row.contact_label,
        # Provider duration (NEWT 511, in seconds) once the journal line is reconciled.
        'journal_status': row.journal_status if row.destination_digest else 'unavailable',
        'journal_started_at': row.journal_started_at,
        'journal_duration': row.journal_duration,
    }
    if administrator:
        result['journal_uid'] = row.journal_uid
        result['caller'] = {'id': row.user_id, 'username': row.user.username}
        result['extension'] = row.extension
    return result


@api_view(['GET'])
def history(request, workspace):
    role = role_in(request.user, workspace)
    rows = (
        PhoneCallAttempt.objects.filter(workspace=workspace)
        .select_related('user')
        .order_by('-created_at', '-pk')
    )
    administrator = role == 'administrator'
    contact = request.query_params.get('contact_id', '')
    if contact:
        if not administrator:
            raise PermissionDenied('Filtre par fiche réservé aux administrateurs.')
        if not contact.isascii() or not contact.isdigit() or len(contact) > 18 or int(contact) < 1:
            raise ValidationError('Fiche invalide.')
        rows = rows.filter(contact_id=int(contact))
    if not administrator:
        rows = rows.filter(user=request.user)
    caller = request.query_params.get('user_id', '')
    if caller:
        if not administrator:
            raise PermissionDenied('Filtre par appelant réservé aux administrateurs.')
        if not caller.isdigit():
            raise ValidationError('Appelant invalide.')
        rows = rows.filter(user_id=int(caller))
    state = request.query_params.get('state', '')
    if state:
        if state not in STATES:
            raise ValidationError('État invalide.')
        rows = rows.filter(state=state)
    pager = Pager()
    page = pager.paginate_queryset(rows, request)
    response = pager.get_paginated_response([output(row, administrator) for row in page])
    response['Cache-Control'] = 'no-store'
    return response


@api_view(['GET'])
def recording(request, workspace, request_id):
    """Stream one recording to an administrator of the matching workspace only."""
    require_admin(request.user, workspace)
    row = PhoneCallAttempt.objects.filter(request_id=request_id, workspace=workspace).first()
    if row is None or not row.journal_uid:
        raise ValidationError('Enregistrement indisponible pour cet appel.')
    try:
        content, content_type = fetch_recording(
            settings.NEWT_USERNAME, settings.NEWT_PASSWORD, row.journal_uid
        )
    except DirectoryUnavailable as error:
        problem = getattr(error, 'diagnostic', {}).get('problem', 'unknown')
        logger.warning(
            'NEWT recording fetch failed workspace=%s request_id=%s problem=%s content_type=%s response_bytes=%s signature=%s',
            workspace,
            request_id,
            problem,
            getattr(error, 'diagnostic', {}).get('content_type', '-'),
            getattr(error, 'diagnostic', {}).get('response_bytes', '-'),
            getattr(error, 'diagnostic', {}).get('signature', '-'),
        )
        if problem.startswith('http_') and problem.removeprefix('http_').isdigit():
            status = problem.removeprefix('http_')
            message = f'NEWT a refusé l’enregistrement (HTTP {status}).'
            if status in ('401', '403'):
                message += ' Vérifiez les identifiants API et les droits de lecture du PBX.'
            elif status == '404':
                message += ' L’enregistrement est absent ou inaccessible pour ce compte NEWT.'
        else:
            message = {
                'recording_uid': 'L’identifiant NEWT de cet enregistrement est invalide.',
                'recording_too_large': 'L’enregistrement NEWT dépasse la taille autorisée.',
                'recording_format': (
                    'NEWT a renvoyé un contenu non audio '
                    f'(type {getattr(error, "diagnostic", {}).get("content_type", "inconnu")}, '
                    f'{getattr(error, "diagnostic", {}).get("response_bytes", "taille inconnue")} octets, '
                    f'{getattr(error, "diagnostic", {}).get("signature", "signature inconnue")}).'
                ),
                'network': 'Le serveur n’a pas pu joindre le service d’enregistrement NEWT.',
            }.get(problem, 'NEWT n’a pas fourni cet enregistrement (cause non reconnue).')
        raise ValidationError(message) from error
    response = HttpResponse(content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="call-{row.request_id}.audio"'
    response['Cache-Control'] = 'no-store'
    return response
