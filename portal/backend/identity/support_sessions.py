from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from packages.support_audit import record_attempt

from .models import AccessAudit, Membership, ROLES

KEY = 'platform_support'
STOP_PATH = '/api/portal/platform/support/stop/'
SWITCH_PATH = '/api/portal/platform/support/switch/'
ACCOUNTS_PATH = '/api/portal/platform/accounts/'
CSRF_PATH = '/api/portal/csrf/'
DURATION = 15 * 60


class StartInput(serializers.Serializer):
    workspace = serializers.ChoiceField(choices=tuple(ROLES))
    reason = serializers.CharField(min_length=3, max_length=500)


class SwitchInput(StartInput):
    user_id = serializers.IntegerField(min_value=1)


def support_membership(user_id, workspace):
    return (
        Membership.objects.select_related('user')
        .filter(
            user_id=user_id,
            workspace=workspace,
            active=True,
            user__is_active=True,
            user__is_superuser=False,
            user__is_staff=False,
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
    opened = AccessAudit.objects.create(
        user=request.user,
        workspace=workspace,
        action='platform.support_started',
        metadata={**context, 'reason': data['reason'], 'journal': True},
    )
    context['id'] = opened.pk
    request.session.cycle_key()
    request.session[KEY] = context
    return session_payload(member.user, support=context)


def finish_support(request, actor, context):
    AccessAudit.objects.create(
        user=actor,
        workspace=context['workspace'],
        action='platform.support_ended',
        metadata={'subject': context['subject'], 'session_id': context.get('id')},
    )
    request.session.pop(KEY)
    request.session.cycle_key()


@api_view(['POST'])
def stop_support(request):
    context = request.session.get(KEY)
    if context is not None:
        finish_support(request, request.user, context)
    return Response(status=204, headers={'Cache-Control': 'no-store'})


@api_view(['POST'])
def switch_support(request):
    """End the current support target and begin another audited session."""
    from .platform_overview import require_superadmin
    from .views import session_payload

    context = request.session.get(KEY)
    if context is None:
        raise ValidationError('Aucune session d’assistance à remplacer.')
    require_superadmin(request)
    serializer = SwitchInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    workspace = data['workspace']
    member = support_membership(data['user_id'], workspace)
    if member is None:
        raise PermissionDenied('Compte ou accès indisponible pour l’assistance.')

    with transaction.atomic():
        AccessAudit.objects.create(
            user=request.user,
            workspace=context['workspace'],
            action='platform.support_ended',
            metadata={
                'subject': context['subject'],
                'session_id': context.get('id'),
                'switched_to': member.user_id,
            },
        )
        next_context = {
            'subject': member.user_id,
            'workspace': workspace,
            'expires': int(timezone.now().timestamp()) + DURATION,
        }
        opened = AccessAudit.objects.create(
            user=request.user,
            workspace=workspace,
            action='platform.support_started',
            metadata={**next_context, 'reason': data['reason'], 'journal': True},
        )
        next_context['id'] = opened.pk
    request.session.cycle_key()
    request.session[KEY] = next_context
    return session_payload(member.user, support=next_context)


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
        record_attempt(
            request,
            AccessAudit,
            user=actor,
            workspace=workspace,
            subject=member.user_id,
            session_id=context.get('id'),
        )
    return member.user, context
