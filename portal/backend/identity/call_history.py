"""Call history: setters read their own call commands, administrators the whole workspace."""

from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from .models import Membership, PhoneCallAttempt

STATES = ('dispatching', 'accepted', 'rejected', 'blocked', 'unknown')


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
    }
    if administrator:
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
