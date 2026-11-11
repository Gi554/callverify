from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .models import AccessAudit, Membership, ROLES

KEY = 'platform_support'
STOP_PATH = '/api/portal/platform/support/stop/'
DURATION = 15 * 60


class StartInput(serializers.Serializer):
    workspace = serializers.ChoiceField(choices=tuple(ROLES))
    reason = serializers.CharField(min_length=3, max_length=500)


def support_membership(user_id, workspace):
    return (
        Membership.objects.select_related('user')
        .filter(
            user_id=user_id,
            workspace=workspace,
            active=True,
            user__is_active=True,
            user__is_superuser=False,
            role__in=ROLES.get(workspace, ()),
        )
        .first()
    )


@api_view(['POST'])
def start_support(request, pk):
    from .platform_overview import require_superadmin
    from .views import session_payload

    require_superadmin(request)
    if KEY in request.session:
        raise ValidationError('Terminez la session d’assistance en cours.')
    serializer = StartInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    workspace = data['workspace']
    member = support_membership(pk, workspace)
    if member is None or pk == request.user.pk:
        raise PermissionDenied('Compte ou accès indisponible pour l’assistance.')
    context = {
        'subject': pk,
        'workspace': workspace,
        'expires': int(timezone.now().timestamp()) + DURATION,
    }
    AccessAudit.objects.create(
        user=request.user,
        workspace=workspace,
        action='platform.support_started',
        metadata={**context, 'reason': data['reason']},
    )
    request.session.cycle_key()
    request.session[KEY] = context
    return session_payload(member.user, support=context)


def finish_support(request, actor, context):
    AccessAudit.objects.create(
        user=actor,
        workspace=context['workspace'],
        action='platform.support_ended',
        metadata={'subject': context['subject']},
    )
    request.session.pop(KEY)
    request.session.cycle_key()


@api_view(['POST'])
def stop_support(request):
    context = request.session.get(KEY)
    if context is not None:
        finish_support(request, request.user, context)
    return Response(status=204, headers={'Cache-Control': 'no-store'})


def authenticate_support(request, actor, context):
    workspace = context['workspace']
    member = support_membership(context['subject'], workspace)
    path = request.path
    session_view = path == '/api/portal/session/' and request.method == 'GET'
    if not actor.is_superuser or member is None or context['expires'] <= timezone.now().timestamp():
        if session_view:
            finish_support(request, actor, context)
            return actor, None
        raise PermissionDenied('Session d’assistance terminée. Revenez au compte superadmin.')
    if session_view:
        return member.user, context
    if path == f'/api/portal/access/{workspace}/':
        return member.user, {**context, 'actor': actor.pk}
    if not path.startswith(f'/api/portal/{workspace}/'):
        raise PermissionDenied('Cette opération est indisponible pendant une session d’assistance.')
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        AccessAudit.objects.create(
            user=actor,
            workspace=workspace,
            action='platform.support_action',
            metadata={'subject': member.user_id, 'method': request.method, 'path': path[:200]},
        )
    return member.user, context
