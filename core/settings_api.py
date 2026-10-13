from django.conf import settings
from django.db import connection
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .permissions import SuperAdminOnly
from .models import PlatformSettings, LookupCheck, ImportBatch, ExportJob, AuditEvent, TaskDelivery, Campaign
from .views import audit

class SettingsSerializer(serializers.ModelSerializer):
    lookup_rate=serializers.IntegerField(min_value=1,max_value=50)
    lookup_cache_hours=serializers.IntegerField(min_value=1,max_value=8760)
    export_hours=serializers.IntegerField(min_value=1,max_value=168)
    import_retention_days=serializers.IntegerField(min_value=1,max_value=3650)
    currency=serializers.ChoiceField(choices=['CAD','USD','EUR'])
    class Meta:
        model=PlatformSettings
        exclude=['id']

@api_view(['GET','PATCH'])
@permission_classes([SuperAdminOnly])
def platform_settings(request):
    obj,_=PlatformSettings.objects.get_or_create(pk=1)
    if request.method=='PATCH':
        serializer=SettingsSerializer(obj,data=request.data,partial=True)
        serializer.is_valid(raise_exception=True);serializer.save()
        audit(request.user,'settings.updated',obj,serializer.validated_data)
    return Response({'settings':SettingsSerializer(obj).data,'integrations':{
        'lookup_configured':bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN),
        'lookup_enabled':settings.LOOKUP_ENABLED,'voice_enabled':False,
        'smtp_configured':bool(settings.EMAIL_HOST_USER),'s3_enabled':bool(getattr(settings,'STORAGES',{}).get('default',{}).get('BACKEND','').endswith('S3Storage')),
        'mfa_encryption_configured':bool(settings.MFA_ENCRYPTION_KEY),'development':settings.DEBUG},
        'tasks':{'waiting':TaskDelivery.objects.filter(status='pending').count(),'failed':TaskDelivery.objects.filter(status='failed').count()}})

@api_view(['GET'])
def notifications(request):
    campaigns=Campaign.objects.all()
    if not request.user.is_superuser: campaigns=campaigns.filter(owner=request.user)
    items=[]
    for model,kind in [(ImportBatch,'Import'),(LookupCheck,'Vérification'),(ExportJob,'Export')]:
        for obj in model.objects.filter(campaign__in=campaigns,status='error').order_by('-pk')[:10]:
            items.append({'id':f'{kind}-{obj.pk}','message':f'{kind} #{obj.pk} en erreur','campaign':obj.campaign_id,'level':'error'})
    return Response({'items':items})

@api_view(['GET'])
@permission_classes([])
def health(request):
    try:
        with connection.cursor() as cursor: cursor.execute('SELECT 1')
        return Response({'status':'ok'})
    except Exception:
        return Response({'status':'unavailable'},status=503)
