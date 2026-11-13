"""Server-persisted Assurance call-session cursor."""

from django.db import transaction
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError, APIException
from rest_framework.response import Response

from .models import CallSessionProgress
from .prospect_queue import apply_queue, call_block_reason
from .visibility import visible_contacts


class Conflict(APIException):
    status_code = 409
    default_detail = 'La progression de session a changé. Rechargez la session.'
    default_code = 'call_session_conflict'


def state(row):
    return {
        'active': row.active,
        'visited_ids': row.visited_contact_ids,
        'current_id': row.current_contact_id,
        'updated_at': row.updated_at,
    }


def authorize(user):
    if user.role not in ('setter', 'administrator'):
        raise PermissionDenied('Session d’appels réservée aux setters et administrateurs.')


@api_view(['GET', 'POST'])
def call_session(request):
    authorize(request.user)
    row, _ = CallSessionProgress.objects.get_or_create(portal_user_id=request.user.pk)
    if request.method == 'GET':
        return Response(state(row))

    data = request.data
    if not isinstance(data, dict) or set(data) - {'action', 'contact_id'}:
        raise ValidationError('Champs de progression invalides.')
    action = data.get('action')
    if action not in ('start', 'begin', 'complete', 'finish'):
        raise ValidationError('Action de session invalide.')

    with transaction.atomic():
        row = CallSessionProgress.objects.select_for_update().get(pk=row.pk)
        if action == 'start':
            row.active = True
            row.visited_contact_ids = []
            row.current_contact_id = None
        elif action == 'begin':
            try:
                contact_id = int(data.get('contact_id'))
            except (TypeError, ValueError):
                raise ValidationError('Prospect de session invalide.')
            if not row.active:
                raise Conflict('La session n’est pas active.')
            if row.current_contact_id is not None:
                raise Conflict('Une fiche est déjà en cours. Reprenez-la avant de continuer.')
            if contact_id in row.visited_contact_ids:
                raise Conflict('Cette fiche est déjà terminée dans la session.')
            contact = (
                apply_queue(
                    visible_contacts(request.user).filter(assigned_setter_id=request.user.pk),
                    'active',
                )
                .filter(pk=contact_id)
                .first()
            )
            if contact is None or not contact.phone.strip() or call_block_reason(contact):
                raise ValidationError('Cette fiche n’est plus admissible dans la session.')
            row.current_contact_id = contact_id
        elif action == 'complete':
            try:
                contact_id = int(data.get('contact_id'))
            except (TypeError, ValueError):
                raise ValidationError('Prospect de session invalide.')
            if contact_id in row.visited_contact_ids and row.current_contact_id is None:
                return Response(state(row))
            if row.current_contact_id != contact_id:
                raise Conflict('La fiche terminée ne correspond pas à la fiche en cours.')
            row.visited_contact_ids = list(dict.fromkeys([*row.visited_contact_ids, contact_id]))
            row.current_contact_id = None
        else:  # finish
            row.active = False
            row.current_contact_id = None
            row.visited_contact_ids = []
        row.save()
    return Response(state(row))
