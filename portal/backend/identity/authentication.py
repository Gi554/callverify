from django.contrib.auth import logout
from rest_framework.authentication import SessionAuthentication
from .models import SessionGeneration

SESSION_KEY='portal_session_generation'

def generation(user):
    return SessionGeneration.objects.filter(user=user).values_list('generation',flat=True).first() or 0

class CentralSessionAuthentication(SessionAuthentication):
    def authenticate(self,request):
        authenticated=super().authenticate(request)
        if authenticated is None:return None
        user,_=authenticated
        if request.session.get(SESSION_KEY,0)!=generation(user):
            logout(request._request)
            return None
        return authenticated
