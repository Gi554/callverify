from django.contrib.auth import authenticate,login,logout
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect
from rest_framework.decorators import api_view,permission_classes,authentication_classes,throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from .models import Membership,AccessAudit
from packages.access.tickets import issue

class LoginThrottle(AnonRateThrottle):
    scope='portal_login'

@api_view(['GET'])
@permission_classes([AllowAny])
def csrf(request):
    return Response({'csrfToken':get_token(request)})

@csrf_protect
@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
@throttle_classes([LoginThrottle])
def sign_in(request):
    from rest_framework.authentication import SessionAuthentication
    SessionAuthentication().enforce_csrf(request)
    user=authenticate(request,username=request.data.get('username',''),password=request.data.get('password',''))
    if not user or not user.is_active:
        return Response({'detail':'Identifiants incorrects'},status=400)
    login(request,user)
    from .authentication import SESSION_KEY,generation
    request.session[SESSION_KEY]=generation(user)
    AccessAudit.objects.create(user=user,action='session.login')
    return session_payload(user)

def session_payload(user):
    memberships=list(Membership.objects.filter(user=user,active=True).values('workspace','role'))
    return Response({'username':user.username,'workspaces':memberships,
        'admin_workspaces':[row['workspace'] for row in memberships if row['role']=='administrator'],
        'landing':memberships[0]['workspace'] if len(memberships)==1 else None})

@api_view(['GET','POST'])
def session(request):
    if request.method=='POST':
        AccessAudit.objects.create(user=request.user,action='session.logout')
        logout(request)
        return Response(status=204)
    return session_payload(request.user)

@api_view(['POST'])
def access(request,workspace):
    membership=Membership.objects.filter(user=request.user,workspace=workspace,active=True).first()
    if not membership:
        return Response({'detail':'Accès non autorisé à cet espace'},status=403)
    membership.full_clean()
    AccessAudit.objects.create(user=request.user,action='workspace.access',workspace=workspace)
    return Response({'token':issue(request.user.pk,workspace,membership.role),'expires_in':120})
