from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response
import requests

from packages.support_audit import ACTION, issue_read, serialize_actions
from .management_api import AccessPagination
from .models import AccessAudit
from .platform_overview import require_superadmin

OPENED = 'platform.support_started'


@api_view(['GET'])
def sessions(request):
    require_superadmin(request)
    rows = AccessAudit.objects.filter(action=OPENED).select_related('user').order_by('-pk')
    pager = AccessPagination()
    page = pager.paginate_queryset(rows, request)
    users = get_user_model().objects.in_bulk({row.metadata['subject'] for row in page})
    response = pager.get_paginated_response(
        [
            {
                'id': row.pk,
                'actor': row.user.username if row.user else '',
                'subject': row.metadata['subject'],
                'username': users[row.metadata['subject']].username
                if row.metadata['subject'] in users
                else '',
                'workspace': row.workspace,
                'reason': row.metadata.get('reason', ''),
                'started_at': row.created_at,
            }
            for row in page
        ]
    )
    response['Cache-Control'] = 'no-store'
    return response


def fetch_business(workspace, session_id):
    base, prefix = {
        'assurance': (settings.ASSURANCE_INTERNAL_URL, '/api/assurance'),
        'isolation': (settings.ISOLATION_INTERNAL_URL, '/api'),
    }[workspace]
    response = requests.get(
        base.rstrip('/') + prefix + '/internal/support-journal/',
        headers={
            'Authorization': 'Bearer ' + issue_read(workspace, session_id),
            'X-Forwarded-Proto': 'https',
        },
        timeout=(3, 4),
        allow_redirects=False,
    )
    if response.status_code != 200:
        raise ValueError('Journal indisponible.')
    data = response.json()
    if not isinstance(data, dict) or not isinstance(data.get('actions'), list):
        raise ValueError('Journal invalide.')
    return data


@api_view(['GET'])
def session_actions(request, pk):
    require_superadmin(request)
    opened = get_object_or_404(AccessAudit, pk=pk, action=OPENED)
    rows = AccessAudit.objects.filter(workspace=opened.workspace, metadata__session_id=pk)
    ended = rows.filter(action='platform.support_ended').order_by('-pk').first()
    portal = serialize_actions(rows.filter(action=ACTION))
    actions = [{**row, 'source': 'portal'} for row in portal['actions']]
    truncated = portal['truncated']
    unavailable = False
    journal = bool(opened.metadata.get('journal'))
    if journal:
        try:
            business = fetch_business(opened.workspace, pk)
            actions.extend({**row, 'source': opened.workspace} for row in business['actions'])
            truncated |= bool(business.get('truncated'))
        except (requests.RequestException, ValueError, KeyError, TypeError):
            unavailable = True
    actions.sort(key=lambda row: row['created_at'], reverse=True)
    return Response(
        {
            'actions': actions,
            'ended_at': ended.created_at if ended else None,
            'expires': opened.metadata.get('expires'),
            'truncated': truncated,
            'business_unavailable': unavailable,
            'journal': journal,
        },
        headers={'Cache-Control': 'no-store'},
    )
