from django.conf import settings
from django.contrib.auth import logout
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import Membership, PortalMFA, SessionGeneration

SESSION_KEY = 'portal_session_generation'


def generation(user):
    return (
        SessionGeneration.objects.filter(user=user).values_list('generation', flat=True).first()
        or 0
    )


class CentralSessionAuthentication(SessionAuthentication):
    def authenticate(self, request):
        authenticated = super().authenticate(request)
        if authenticated is None:
            return None
        user, _ = authenticated
        if request.session.get(SESSION_KEY, 0) != generation(user):
            logout(request._request)
            return None
        is_admin = Membership.objects.filter(user=user, active=True, role='administrator').exists()
        has_mfa = PortalMFA.objects.filter(user=user, enabled_at__isnull=False).exists()
        if (
            settings.MFA_ENABLED
            and not settings.DEBUG
            and is_admin
            and not has_mfa
            and request.path
            not in (
                '/api/portal/csrf/',
                '/api/portal/session/',
                '/api/portal/mfa/',
            )
        ):
            raise AuthenticationFailed('Activez la MFA pour accéder à votre espace administrateur.')
        return authenticated
