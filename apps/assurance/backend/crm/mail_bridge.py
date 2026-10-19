from datetime import timedelta
from django.utils import timezone
from django.core import signing
from rest_framework.decorators import api_view,authentication_classes,permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied,ValidationError
from rest_framework.response import Response
from packages.access.mail_bridge import verify
from .models import TaskNotification

def authorize(request,operation,**claims):
    token=request.headers.get('Authorization','')
    if not token.startswith('Bearer '):raise PermissionDenied('Échange serveur requis')
    try:verify(token[7:],operation,**claims)
    except (signing.BadSignature,ValueError,TypeError):raise PermissionDenied('Échange serveur invalide ou expiré')

def candidates():
    return TaskNotification.objects.filter(kind__in=['report','incident'],task__closed_at__isnull=True,
        created_at__gte=timezone.now()-timedelta(days=7))

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def events(request):
    try:after=int(request.query_params.get('after','0'))
    except (ValueError,TypeError):raise ValidationError('Curseur invalide')
    if not 0<=after<=9223372036854775807:raise ValidationError('Curseur invalide')
    authorize(request,'events',after=after)
    rows=candidates().filter(pk__gt=after).order_by('pk').values('id','created_at','task__setter_id')[:100]
    response=Response({'events':[{'id':row['id'],'created_at':row['created_at'],'setter_id':row['task__setter_id']} for row in rows]})
    response['Cache-Control']='no-store';return response

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def eligible(request,pk,user_id):
    authorize(request,'eligible',event=pk,user=user_id)
    response=Response({'eligible':candidates().filter(pk=pk,task__setter_id=user_id).exists()})
    response['Cache-Control']='no-store';return response

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def reminder_events(request):
    from .reminders import active
    try:after=int(request.query_params.get('after','0'))
    except (ValueError,TypeError):raise ValidationError('Curseur invalide')
    if not 0<=after<=9223372036854775807:raise ValidationError('Curseur invalide')
    authorize(request,'reminder_events',after=after)
    rows=active().exclude(recipient_role='administrator').filter(pk__gt=after).order_by('pk').values('id','created_at','recipient_id','recipient_role')[:100]
    response=Response({'events':[{'id':row['id'],'created_at':row['created_at'],'recipient_id':row['recipient_id'],'role':row['recipient_role']} for row in rows]})
    response['Cache-Control']='no-store';return response

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def reminder_eligible(request,pk,user_id):
    from .reminders import active
    authorize(request,'reminder_eligible',event=pk,user=user_id)
    response=Response({'eligible':active().exclude(recipient_role='administrator').filter(pk=pk,recipient_id=user_id).exists()})
    response['Cache-Control']='no-store';return response

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def escalation_events(request):
    from .reminders import active,ESCALATIONS
    try:after=int(request.query_params.get('after','0'))
    except (ValueError,TypeError):raise ValidationError('Curseur invalide')
    if not 0<=after<=9223372036854775807:raise ValidationError('Curseur invalide')
    authorize(request,'escalation_events',after=after)
    rows=active().filter(kind__in=ESCALATIONS,pk__gt=after).order_by('pk').values('id','created_at')[:100]
    response=Response({'events':[{'id':row['id'],'created_at':row['created_at'],'recipient_id':0,'role':'administrator'} for row in rows]})
    response['Cache-Control']='no-store';return response

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def escalation_eligible(request,pk,user_id):
    from .reminders import active,ESCALATIONS
    authorize(request,'escalation_eligible',event=pk,user=user_id)
    # Central administrator membership is checked by the portal; Assurance has no account database.
    response=Response({'eligible':active().filter(pk=pk,kind__in=ESCALATIONS).exists()})
    response['Cache-Control']='no-store';return response
