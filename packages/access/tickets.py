"""Short-lived audience-bound tickets; separate key for each CRM."""
import os
from django.conf import settings
from django.core import signing
from django.core.exceptions import ImproperlyConfigured

def key_for(workspace):
    if workspace not in {'assurance','isolation'}:
        raise signing.BadSignature('Unknown audience')
    key = os.getenv(f'{workspace.upper()}_ACCESS_KEY','')
    if not key:
        if not settings.DEBUG:
            raise ImproperlyConfigured(f'{workspace.upper()}_ACCESS_KEY required')
        key = f'local-{workspace}-access-development-only'
    return key

def issue(user_id, workspace, role):
    return signing.dumps({'sub':str(user_id),'aud':workspace,'role':role},key=key_for(workspace),salt='amx.workspace.v1')

def verify(token, workspace):
    claims = signing.loads(token,key=key_for(workspace),salt='amx.workspace.v1',max_age=120)
    roles = {'assurance':{'administrator','setter','advisor'},'isolation':{'administrator','setter','client'}}
    if claims.get('aud') != workspace or claims.get('role') not in roles[workspace] or not str(claims.get('sub','')).isdigit():
        raise signing.BadSignature('Invalid workspace claims')
    return claims
