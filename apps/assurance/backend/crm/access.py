from dataclasses import dataclass
from django.core import signing
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from packages.access.tickets import verify
from packages.support_audit import record_attempt


@dataclass(frozen=True)
class Identity:
    pk: int
    role: str
    is_authenticated: bool = True
    is_active: bool = True


class WorkspaceAuthentication(BaseAuthentication):
    def authenticate_header(self, request):
        return 'Bearer'

    def authenticate(self, request):
        header = get_authorization_header(request).split()
        if not header:
            return None
        if len(header) != 2 or header[0].lower() != b'bearer':
            raise AuthenticationFailed('Jeton requis')
        try:
            claims = verify(header[1].decode(), 'assurance')
        except (signing.BadSignature, UnicodeDecodeError, ValueError, TypeError):
            raise AuthenticationFailed('Accès Assurance invalide ou expiré')
        if 'support_actor' in claims and request.method not in ('GET', 'HEAD', 'OPTIONS'):
            from .models import BusinessAudit

            record_attempt(
                request,
                BusinessAudit,
                actor_id=claims['support_actor'],
                object_id=int(claims['sub']),
                session_id=claims.get('support_session'),
            )
        return Identity(pk=int(claims['sub']), role=claims['role']), claims
