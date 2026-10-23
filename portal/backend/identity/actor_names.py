"""Resolve visible workspace identities for administrator audit displays."""

from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from .management_api import require_admin
from .models import Membership


@api_view(['GET'])
def names(request, workspace):
    require_admin(request.user, workspace)
    raw = request.query_params.get('ids', '').split(',')
    if (
        set(request.query_params) != {'ids'}
        or not 1 <= len(raw) <= 25
        or any(not item.isdigit() or len(item) > 18 or int(item) < 1 for item in raw)
    ):
        raise ValidationError('De 1 à 25 identifiants de comptes attendus.')
    rows = (
        Membership.objects.filter(workspace=workspace, user_id__in=[int(item) for item in raw])
        .select_related('user')
        .order_by('user_id')
    )
    response = Response(
        {
            'results': [
                {'id': row.user_id, 'name': row.user.get_full_name().strip() or row.user.username}
                for row in rows
            ]
        }
    )
    response['Cache-Control'] = 'no-store'
    return response
