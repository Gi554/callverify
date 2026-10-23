"""Client accounts, including inactive historical accounts, scoped to an admin's space."""

from django.db.models import Q
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination
from .management_api import require_admin
from .models import Membership


@api_view(['GET'])
def clients(request, workspace):
    require_admin(request.user, workspace)
    role = 'advisor' if workspace == 'assurance' else 'client'
    rows = Membership.objects.filter(workspace=workspace, role=role).select_related('user')
    term = request.query_params.get('search', '').strip()[:150]
    if term:
        rows = rows.filter(
            Q(user__username__icontains=term)
            | Q(user__first_name__icontains=term)
            | Q(user__last_name__icontains=term)
        )
    pager = PageNumberPagination()
    pager.page_size = 12
    page = pager.paginate_queryset(rows.order_by('user__username', 'pk'), request)
    response = pager.get_paginated_response(
        [
            {
                'id': row.user_id,
                'name': row.user.get_full_name().strip() or row.user.username,
                'active': row.active and row.user.is_active,
                'quota': row.prospect_quota if workspace == 'assurance' else None,
            }
            for row in page
        ]
    )
    response['Cache-Control'] = 'no-store'
    return response
