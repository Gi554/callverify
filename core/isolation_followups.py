"""Declared call outcomes and owned callbacks. Never dispatches a call."""
import hashlib
import json
from uuid import uuid4
from django.db import transaction
from django.db.models import F,Min
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers,viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from .models import Prospect,ProspectActivity,IsolationFollowUp,IsolationVisit,AuditEvent

RESULTS={'appointment_booked':'Rendez-vous pris','voicemail':'Répondeur','invalid_number':'Numéro invalide déclaré',
    'disconnected':'Appel coupé','not_interested':'Pas intéressé','callback':'Rappel demandé','unreachable':'Injoignable'}

def fingerprint(data):return hashlib.sha256(json.dumps(data,sort_keys=True,default=str).encode()).hexdigest()

def explicit(value,raw,future=True):
    try:parsed=parse_datetime(str(raw))
    except (ValueError,TypeError):parsed=None
    if parsed is None or timezone.is_naive(parsed):raise ValidationError('Date ISO 8601 avec décalage explicite requise.')
    if future and value<=timezone.now():raise ValidationError('Le rappel doit être dans le futur.')

def sync(prospect):
    earliest=IsolationFollowUp.objects.filter(prospect=prospect,closed_at__isnull=True).aggregate(value=Min('due_at'))['value']
    Prospect.objects.filter(pk=prospect.pk).update(callback_at=earliest)

def event(prospect,user,kind,note,changes,request_id=None):
    row=ProspectActivity.objects.create(prospect=prospect,request_id=request_id or uuid4(),fingerprint=fingerprint(changes),
        author_portal_id=user.pk,author_role=user.role,kind=kind,body=note,changes=changes)
    AuditEvent.objects.create(action='isolation.prospect.'+kind,object_id=str(prospect.pk),
        metadata={'actor_portal_id':user.pk,'activity_id':row.pk,'changes':changes})
    return row

def output(row):
    return {'id':row.pk,'prospect_id':row.prospect_id,'prospect_name':row.prospect.name,'due_at':row.due_at,
        'owner_name':row.prospect.assigned_setter_name,'note':row.note,'revision':row.revision,'closed_at':row.closed_at,'resolution':row.resolution,
        'created_by_id':row.created_by_id,'owner_id':row.prospect.assigned_setter_id,
        'overdue':row.closed_at is None and row.due_at<timezone.now()}

def lock(prospect,user,revision=None):
    from .isolation_work import Conflict
    rows=Prospect.objects.filter(pk=prospect.pk)
    if user.role=='setter':rows=rows.filter(assigned_setter_id=user.pk)
    if revision is not None:rows=rows.filter(assignment_revision=revision)
    if not rows.update(assignment_revision=F('assignment_revision')+1):raise Conflict('Prospect modifié ou réattribué : actualisez.')
    return Prospect.objects.get(pk=prospect.pk)

class Strict(serializers.Serializer):
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise ValidationError('Champs non autorisés.')
        return data

class TaskInput(Strict):
    request_id=serializers.UUIDField()
    revision=serializers.IntegerField(min_value=0)
    note=serializers.CharField(max_length=3000,allow_blank=True,default='')
    due_at=serializers.DateTimeField()
    def validate(self,data):
        super().validate(data);explicit(data['due_at'],self.initial_data['due_at'],future=False);return data

class CallInput(Strict):
    request_id=serializers.UUIDField()
    revision=serializers.IntegerField(min_value=0)
    result=serializers.ChoiceField(choices=list(RESULTS))
    note=serializers.CharField(max_length=3000,allow_blank=True,default='')
    due_at=serializers.DateTimeField(required=False)
    appointment_id=serializers.IntegerField(min_value=1,required=False)
    def validate(self,data):
        super().validate(data)
        if data['result']=='callback':
            if not data.get('due_at'):raise ValidationError('Date et heure de rappel requises.')
            explicit(data['due_at'],self.initial_data['due_at'],future=False)
        elif 'due_at' in data:raise ValidationError('Date réservée au résultat Rappel demandé.')
        if (data['result']=='appointment_booked')!=('appointment_id' in data):raise ValidationError('Rendez-vous pris : liez une réservation existante ; aucun autre résultat ne reçoit de rendez-vous.')
        return data

class FollowUpMixin:
    @action(detail=True,methods=['get','post'],url_path='follow-ups')
    def follow_ups(self,request,pk=None):
        from .isolation_work import Conflict
        prospect=self.get_object()
        if request.method=='GET':
            rows=IsolationFollowUp.objects.filter(prospect=prospect).select_related('prospect').order_by('closed_at','due_at','pk')
            response=self.get_paginated_response([output(row) for row in self.paginate_queryset(rows)]);response['Cache-Control']='no-store';return response
        serializer=TaskInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
        value=fingerprint({key:data[key] for key in ('note','due_at')})
        with transaction.atomic():
            # Lock ownership before replay; transfers revoke former owners even for retries.
            current=lock(prospect,request.user)
            old=IsolationFollowUp.objects.select_related('prospect').filter(request_id=data['request_id']).first()
            if old:
                transaction.set_rollback(True)
                if (old.prospect_id,old.created_by_id,old.fingerprint)!=(prospect.pk,request.user.pk,value):raise Conflict('Identifiant de rappel déjà utilisé.')
                return Response(output(old))
            if prospect.assignment_revision!=data['revision']:raise Conflict('Prospect modifié : actualisez.')
            explicit(data['due_at'],request.data['due_at'])
            row=IsolationFollowUp.objects.create(prospect=current,request_id=data['request_id'],fingerprint=value,
                created_by_id=request.user.pk,note=data['note'],due_at=data['due_at'])
            event(current,request.user,'callback_created',row.note,{'task_id':row.pk,'due_at':row.due_at.isoformat()});sync(current)
        return Response(output(row),status=201)

    @action(detail=True,methods=['post'],url_path='call-result')
    def call_result(self,request,pk=None):
        from .isolation_work import Conflict
        from .isolation_activity import output as activity_output
        prospect=self.get_object();serializer=CallInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
        values={key:value for key,value in data.items() if key not in ('revision','request_id')};value=fingerprint(values)
        with transaction.atomic():
            current=lock(prospect,request.user)
            old=ProspectActivity.objects.filter(request_id=data['request_id']).first()
            if old:
                transaction.set_rollback(True)
                if old.prospect_id!=prospect.pk or old.author_portal_id!=request.user.pk or old.kind!='call_result' or old.changes.get('fingerprint')!=value:raise Conflict('Identifiant de résultat déjà utilisé.')
                return Response(activity_output(old))
            if prospect.assignment_revision!=data['revision']:raise Conflict('Prospect modifié : actualisez.')
            if data['result']=='appointment_booked':
                visits=IsolationVisit.objects.filter(pk=data['appointment_id'],prospect=current,status='scheduled')
                if request.user.role=='setter':visits=visits.filter(setter_id=request.user.pk)
                if not visits.exists():raise ValidationError('Réservation autorisée existante requise pour ce prospect.')
            changes={'result':data['result'],'fingerprint':value,'phone':current.raw_phone}
            if 'appointment_id' in data:changes['appointment_id']=data['appointment_id']
            if data['result']=='callback':
                explicit(data['due_at'],request.data['due_at'])
                task=IsolationFollowUp.objects.create(prospect=current,request_id=uuid4(),fingerprint=value,
                    created_by_id=request.user.pk,note=data['note'],due_at=data['due_at'])
                changes.update(task_id=task.pk,due_at=task.due_at.isoformat());sync(current)
            row=event(current,request.user,'call_result',data['note'],changes,data['request_id'])
        return Response(activity_output(row),status=201)

class EditInput(Strict):
    revision=serializers.IntegerField(min_value=0)
    note=serializers.CharField(max_length=3000,allow_blank=True)
    due_at=serializers.DateTimeField()
    def validate(self,data):
        super().validate(data);explicit(data['due_at'],self.initial_data['due_at']);return data

class CloseInput(Strict):
    revision=serializers.IntegerField(min_value=0)
    resolution=serializers.CharField(max_length=3000)

# Imported at the end: WorkAuthentication is defined before this viewset is loaded by urls.
from .isolation_work import WorkAuthentication,Pager,Conflict

class FollowUps(viewsets.GenericViewSet):
    authentication_classes=[WorkAuthentication]
    permission_classes=[IsAuthenticated]
    serializer_class=EditInput
    pagination_class=Pager
    http_method_names=['get','post','head','options']
    def get_queryset(self):
        rows=IsolationFollowUp.objects.select_related('prospect').order_by('closed_at','due_at','pk')
        if self.request.user.role=='setter':rows=rows.filter(prospect__assigned_setter_id=self.request.user.pk)
        prospect=self.request.query_params.get('prospect_id','')
        if prospect:
            if not prospect.isdigit():raise ValidationError('Prospect invalide.')
            rows=rows.filter(prospect_id=int(prospect))
        term=self.request.query_params.get('search','').strip()[:250]
        if term:
            from django.db.models import Q
            rows=rows.filter(Q(prospect__name__icontains=term)|Q(prospect__raw_phone__icontains=term)|Q(note__icontains=term))
        state=self.request.query_params.get('state','open')
        if state not in ('open','closed','all','overdue','upcoming'):raise ValidationError('État invalide.')
        if state=='closed':rows=rows.filter(closed_at__isnull=False)
        elif state!='all':rows=rows.filter(closed_at__isnull=True)
        if state=='overdue':rows=rows.filter(due_at__lt=timezone.now())
        if state=='upcoming':rows=rows.filter(due_at__gte=timezone.now())
        return rows
    def list(self,request):
        response=self.get_paginated_response([output(row) for row in self.paginate_queryset(self.get_queryset())]);response['Cache-Control']='no-store';return response
    def retrieve(self,request,pk=None):return Response(output(self.get_object()))
    @action(detail=True,methods=['post'])
    def edit(self,request,pk=None):return self.modify(request)
    @action(detail=True,methods=['post'])
    def close(self,request,pk=None):return self.modify(request,close=True)
    def modify(self,request,close=False):
        original=self.get_object();serializer=(CloseInput if close else EditInput)(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
        with transaction.atomic():
            prospect=lock(original.prospect,request.user)
            row=IsolationFollowUp.objects.get(pk=original.pk)
            if row.closed_at or row.revision!=data['revision']:raise Conflict('Rappel modifié ou terminé : actualisez.')
            before={'note':row.note,'due_at':row.due_at.isoformat()}
            if close:row.closed_at=timezone.now();row.closed_by_id=request.user.pk;row.resolution=data['resolution']
            else:row.note=data['note'];row.due_at=data['due_at']
            row.revision+=1;row.save()
            event(prospect,request.user,'callback_closed' if close else 'callback_updated',row.resolution if close else row.note,
                {'task_id':row.pk,'before':before,'after':{'note':row.note,'due_at':row.due_at.isoformat(),'closed_at':row.closed_at.isoformat() if row.closed_at else None}})
            sync(prospect)
        return Response(output(row))
