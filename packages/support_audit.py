import logging

from django.core import signing
from django.db import DatabaseError

from .access.tickets import key_for

ACTION = 'platform.support_action'
LIMIT = 100
SALT = 'amx.support-journal.v1'
logger = logging.getLogger(__name__)


def record_attempt(
    request, model, *, session_id=None, subject=None, actor_portal_id=None, **fields
):
    row = model.objects.create(
        action=ACTION,
        metadata={
            'method': request.method,
            'path': request.path[:200],
            'session_id': session_id,
            **({'subject': subject} if subject is not None else {}),
            **({'actor_portal_id': actor_portal_id} if actor_portal_id is not None else {}),
        },
        **fields,
    )
    request._request.support_audit_entry = row


class SupportAuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        row = getattr(request, 'support_audit_entry', None)
        if row is not None:
            row.metadata['status'] = response.status_code
            try:
                row.save(update_fields=['metadata'])
            except DatabaseError:
                logger.warning('Could not record the support action response status')
        return response


def issue_read(workspace, session_id):
    return signing.dumps(session_id, key=key_for(workspace), salt=SALT)


def serialize_actions(rows):
    entries = list(rows.order_by('-pk')[: LIMIT + 1])
    return {
        'actions': [
            {
                'id': row.pk,
                'created_at': row.created_at.isoformat(),
                'method': row.metadata.get('method', ''),
                'path': row.metadata.get('path', ''),
                'status': row.metadata.get('status'),
            }
            for row in entries[:LIMIT]
        ],
        'truncated': len(entries) > LIMIT,
    }


def business_journal(request, workspace, model):
    from rest_framework.exceptions import PermissionDenied
    from rest_framework.response import Response

    prefix = 'Bearer '
    authorization = request.headers.get('Authorization', '')
    if not authorization.startswith(prefix):
        raise PermissionDenied('Échange serveur requis.')
    try:
        session_id = signing.loads(
            authorization[len(prefix) :], key=key_for(workspace), salt=SALT, max_age=30
        )
    except (signing.BadSignature, ValueError, TypeError):
        raise PermissionDenied('Échange serveur invalide.') from None
    if type(session_id) is not int or session_id <= 0:
        raise PermissionDenied('Session invalide.')
    rows = model.objects.filter(action=ACTION, metadata__session_id=session_id)
    return Response(serialize_actions(rows), headers={'Cache-Control': 'no-store'})


def business_journal_view(workspace, model):
    from rest_framework.decorators import api_view, authentication_classes, permission_classes
    from rest_framework.permissions import AllowAny

    @api_view(['GET'])
    @authentication_classes([])
    @permission_classes([AllowAny])
    def view(request):
        return business_journal(request, workspace, model)

    return view
