"""Central identity adapter. Legacy session authentication remains available."""
from django.core import signing
from rest_framework.authentication import BaseAuthentication,get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from packages.access.tickets import verify
from .models import AdminUser

class WorkspaceAuthentication(BaseAuthentication):
    def authenticate(self,request):
        header=get_authorization_header(request).split()
        if not header:return None
        if len(header)!=2 or header[0].lower()!=b'bearer':raise AuthenticationFailed('Jeton requis')
        try:claims=verify(header[1].decode(),'isolation')
        except (signing.BadSignature,UnicodeDecodeError,ValueError,TypeError):raise AuthenticationFailed('Accès Isolation invalide ou expiré')
        # Legacy administrative APIs stay closed to setters; their work queue
        # uses the scoped authentication in isolation_work.py instead.
        if claims['role']!='administrator':raise AuthenticationFailed('API administrative Isolation réservée aux administrateurs')
        user,created=AdminUser.objects.get_or_create(username=f'portal:{claims["sub"]}',defaults={'is_staff':True,'is_superuser':True})
        if created:
            user.set_unusable_password();user.save(update_fields=['password'])
        if not user.is_active:raise AuthenticationFailed('Compte suspendu')
        return user,claims
