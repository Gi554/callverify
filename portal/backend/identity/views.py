from django.contrib.auth import authenticate, login, logout
from django.conf import settings
from django.db import transaction
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect
from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from .models import Membership, AccessAudit, PortalMFA, ROLES
from packages.access.tickets import issue
from .mfa import admin_requires_mfa, authenticate_code, mfa_enabled


class LoginThrottle(AnonRateThrottle):
    scope = 'portal_login'


class MFALoginThrottle(AnonRateThrottle):
    scope = 'portal_mfa_login'

    def allow_request(self, request, view):
        if not request.data.get('code'):
            return True
        return super().allow_request(request, view)


@api_view(['GET'])
@permission_classes([AllowAny])
def csrf(request):
    return Response({'csrfToken': get_token(request)})


@csrf_protect
@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
@throttle_classes([LoginThrottle, MFALoginThrottle])
def sign_in(request):
    from rest_framework.authentication import SessionAuthentication

    SessionAuthentication().enforce_csrf(request)
    if set(request.data) - {'username', 'password', 'workspace', 'code'}:
        return Response({'detail': 'Champs de connexion non autorisés'}, status=400)
    user = authenticate(
        request,
        username=request.data.get('username', ''),
        password=request.data.get('password', ''),
    )
    if not user or not user.is_active:
        return Response({'detail': 'Identifiants incorrects'}, status=400)
    workspace = request.data.get('workspace')
    if workspace is not None:
        if workspace not in ('assurance', 'isolation'):
            return Response({'detail': 'Profil inconnu'}, status=400)
        if not Membership.objects.filter(
            user=user, workspace=workspace, active=True, role__in=ROLES[workspace]
        ).exists():
            return Response({'detail': 'Votre compte n’a pas accès à ce profil.'}, status=403)
    factor = (
        PortalMFA.objects.filter(user=user, enabled_at__isnull=False).first()
        if settings.MFA_ENABLED
        else None
    )
    if factor:
        with transaction.atomic():
            factor = PortalMFA.objects.select_for_update().get(pk=factor.pk)
            if not authenticate_code(factor, request.data.get('code', '')):
                return Response(
                    {
                        'detail': 'Code de sécurité requis, invalide ou déjà utilisé.',
                        'mfa_required': True,
                    },
                    status=401,
                )
            AccessAudit.objects.create(user=user, action='session.mfa_login')
    login(request, user)
    from .authentication import SESSION_KEY, generation

    request.session[SESSION_KEY] = generation(user)
    if admin_requires_mfa(user) and not factor:
        request.session['portal_mfa_setup_required'] = True
    else:
        request.session.pop('portal_mfa_setup_required', None)
    AccessAudit.objects.create(user=user, action='session.login')
    return session_payload(
        user, setup_required=bool(request.session.get('portal_mfa_setup_required'))
    )


def session_payload(user, setup_required=None):
    memberships = list(
        Membership.objects.filter(user=user, active=True)
        .exclude(role='closer')
        .values('workspace', 'role')
    )
    return Response(
        {
            'username': user.username,
            'workspaces': memberships,
            'admin_workspaces': [
                row['workspace'] for row in memberships if row['role'] == 'administrator'
            ],
            'landing': memberships[0]['workspace'] if len(memberships) == 1 else None,
            'mfa_enabled': mfa_enabled(user),
            'mfa_required': (
                admin_requires_mfa(user) and not mfa_enabled(user)
                if setup_required is None
                else setup_required
            ),
        }
    )


@api_view(['GET', 'POST'])
def session(request):
    if request.method == 'POST':
        AccessAudit.objects.create(user=request.user, action='session.logout')
        logout(request)
        return Response(status=204)
    return session_payload(request.user)


@api_view(['POST'])
def access(request, workspace):
    membership = Membership.objects.filter(
        user=request.user, workspace=workspace, active=True
    ).first()
    if not membership or membership.role not in ROLES.get(workspace, set()):
        return Response({'detail': 'Accès non autorisé à cet espace'}, status=403)
    membership.full_clean()
    AccessAudit.objects.create(user=request.user, action='workspace.access', workspace=workspace)
    return Response(
        {'token': issue(request.user.pk, workspace, membership.role), 'expires_in': 120}
    )
