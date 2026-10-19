"""Global PBX directory: both workspace administration grants required."""
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.decorators import api_view,throttle_classes
from rest_framework.exceptions import APIException,ValidationError
from rest_framework.throttling import UserRateThrottle
from rest_framework.response import Response
from packages.newt.directory import fetch,DirectoryUnavailable
from .management_api import require_admin
from .models import PhoneDirectoryGate,AccessAudit

class DirectoryThrottle(UserRateThrottle):scope='phone_directory'
class Unavailable(APIException):
    status_code=503
    default_detail='Annuaire NEWT indisponible ou non configuré. Aucune conclusion sur les postes ; associations locales conservées.'

@api_view(['POST'])
@throttle_classes([DirectoryThrottle])
def directory(request):
    for workspace in ('assurance','isolation'):require_admin(request.user,workspace)
    if request.data or request.query_params:raise ValidationError('Aucun paramètre attendu')
    if not settings.NEWT_DIRECTORY_ENABLED or not settings.NEWT_USERNAME or not settings.NEWT_PASSWORD:raise Unavailable()
    try:
        with transaction.atomic():
            PhoneDirectoryGate.objects.get_or_create(pk=1)
            PhoneDirectoryGate.objects.filter(pk=1).update(revision=F('revision'))
            for workspace in ('assurance','isolation'):require_admin(request.user,workspace)
            rows=fetch(settings.NEWT_USERNAME,settings.NEWT_PASSWORD)
            AccessAudit.objects.create(user=request.user,action='phone.directory_read',metadata={'count':len(rows)})
    except DirectoryUnavailable:raise Unavailable() from None
    response=Response({'results':rows,'checked_at':timezone.now(),'source':'NEWT 343','total':len(rows)})
    response['Cache-Control']='no-store';return response
