from datetime import timedelta
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import serializers,viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied,ValidationError
from rest_framework.response import Response
from .models import Appointment,AppointmentReport,FollowUpTask,BusinessAudit,AppointmentIncident
from .leases import Conflict
from .policies import policy
from .notifications import notify
from rest_framework.pagination import PageNumberPagination

class AppointmentPagination(PageNumberPagination):
    page_size=25

class ReportInput(serializers.Serializer):
    revision=serializers.IntegerField(min_value=0)
    performed=serializers.BooleanField()
    problem=serializers.BooleanField(default=False)
    note=serializers.CharField(max_length=3000,allow_blank=True,default='')
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise ValidationError('Champs non autorisés')
        if (not data['performed'] or data['problem']) and not data['note'].strip():raise ValidationError('Précisez le motif du suivi')
        return data

class IncidentInput(serializers.Serializer):
    request_id=serializers.UUIDField()
    note=serializers.CharField(max_length=3000)
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise ValidationError('Champs non autorisés')
        return data

class ReportMixin:
    @action(detail=True,methods=['get','post'])
    def incidents(self,request,pk=None):
        original=self.get_object()
        if request.method=='GET':
            rows=self.paginate_queryset(AppointmentIncident.objects.filter(appointment=original).order_by('-pk'))
            return self.get_paginated_response([{'id':row.pk,'note':row.note,'created_at':row.created_at} for row in rows])
        if request.user.role!='advisor':raise PermissionDenied('Signalement réservé au conseiller du rendez-vous')
        serializer=IncidentInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
        with transaction.atomic():
            Appointment.objects.filter(pk=original.pk).update(revision=F('revision'))
            appointment=Appointment.objects.get(pk=original.pk)
            existing=AppointmentIncident.objects.filter(request_id=data['request_id']).first()
            if existing:
                if existing.appointment_id!=appointment.pk or existing.author_id!=request.user.pk or existing.note!=data['note']:
                    raise Conflict('Identifiant de signalement déjà utilisé')
                return Response({'recorded':True})
            if not AppointmentReport.objects.filter(appointment=appointment).exists():raise Conflict('Renseignez le compte rendu initial avant ce signalement')
            incident,created=AppointmentIncident.objects.get_or_create(request_id=data['request_id'],defaults={'appointment':appointment,'author_id':request.user.pk,'note':data['note']})
            if not created:raise Conflict('Identifiant de signalement déjà utilisé')
            task=FollowUpTask.objects.filter(appointment=appointment).first()
            if task is None:
                rules=policy()
                task=FollowUpTask.objects.create(appointment=appointment,setter_id=appointment.setter_id,reason=data['note'],due_at=timezone.now()+timedelta(hours=rules.initial_hours),priority=rules.default_priority,policy_revision=rules.revision)
            else:
                # Conditional write serializes reopening with planning and closure.
                FollowUpTask.objects.filter(pk=task.pk).update(revision=F('revision'))
                task.refresh_from_db()
                before={'closed_at':task.closed_at.isoformat() if task.closed_at else None,'resolution':task.resolution,'revision':task.revision}
                if task.closed_at:
                    rules=policy()
                    task.closed_at=None;task.closed_by_id=None;task.resolution='';task.due_at=timezone.now()+timedelta(hours=rules.reopen_hours);task.policy_revision=rules.revision
                task.revision+=1;task.save(update_fields=['closed_at','closed_by_id','resolution','due_at','revision','policy_revision'])
                BusinessAudit.objects.create(actor_id=request.user.pk,object_id=appointment.pk,action='appointment.follow_up_incident',
                    metadata={'task_id':task.pk,'incident_id':incident.pk,'before':before,'revision':task.revision})
            BusinessAudit.objects.create(actor_id=request.user.pk,object_id=appointment.pk,action='appointment.incident_reported',
                metadata={'task_id':task.pk,'incident_id':incident.pk,'note':data['note']})
            notify(task,'incident',f'incident:{incident.pk}')
        return Response({'recorded':True},status=201)

    @action(detail=True,methods=['get','post'])
    def report(self,request,pk=None):
        original=self.get_object()
        if request.method=='GET':
            row=AppointmentReport.objects.filter(appointment=original).first()
            return Response(None if not row else {'performed':row.performed,'problem':row.problem,'note':row.note,'created_at':row.created_at})
        if request.user.role!='advisor':raise PermissionDenied('Compte rendu réservé au conseiller du rendez-vous')
        serializer=ReportInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
        with transaction.atomic():
            Appointment.objects.filter(pk=original.pk).update(revision=F('revision'))
            appointment=Appointment.objects.get(pk=original.pk)
            existing=AppointmentReport.objects.filter(appointment=appointment).first()
            if existing:
                if any(getattr(existing,key)!=data[key] for key in ('performed','problem','note')):raise Conflict('Compte rendu déjà enregistré ; historique conservé')
                return Response({'recorded':True})
            if appointment.status!='scheduled' or appointment.ends_at>timezone.now():raise Conflict('Compte rendu attendu après la fin d’un rendez-vous non annulé')
            if appointment.revision!=data['revision']:raise Conflict('Rendez-vous modifié : actualisez avant de répondre')
            row=AppointmentReport.objects.create(appointment=appointment,author_id=request.user.pk,
                **{key:data[key] for key in ('performed','problem','note')})
            if not row.performed or row.problem:
                rules=policy()
                task=FollowUpTask.objects.create(appointment=appointment,setter_id=appointment.setter_id,reason=row.note,
                    due_at=timezone.now()+timedelta(hours=rules.initial_hours),priority=rules.default_priority,policy_revision=rules.revision)
                notify(task,'report',f'report:{row.pk}')
            BusinessAudit.objects.create(actor_id=request.user.pk,object_id=appointment.pk,action='appointment.reported',
                metadata={'performed':row.performed,'problem':row.problem})
        return Response({'recorded':True},status=201)

class CloseInput(serializers.Serializer):
    revision=serializers.IntegerField(min_value=0)
    resolution=serializers.CharField(max_length=3000)
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise ValidationError('Champs non autorisés')
        return data

class TaskPlanInput(serializers.Serializer):
    revision=serializers.IntegerField(min_value=0)
    priority=serializers.ChoiceField(choices=['low','normal','high','urgent'])
    due_at=serializers.DateTimeField()
    reason=serializers.CharField(max_length=1000)
    def validate(self,data):
        from django.utils.dateparse import parse_datetime
        if set(self.initial_data)-set(self.fields):raise ValidationError('Champs non autorisés')
        raw=parse_datetime(str(self.initial_data['due_at']))
        if raw is None or timezone.is_naive(raw):raise ValidationError('Échéance ISO 8601 avec décalage explicite requise')
        if data['due_at']<=timezone.now():raise ValidationError('La nouvelle échéance doit être dans le futur')
        return data

class TaskOwnerInput(serializers.Serializer):
    revision=serializers.IntegerField(min_value=0)
    proof=serializers.CharField(max_length=3000)
    reason=serializers.CharField(max_length=1000)
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise ValidationError('Champs non autorisés')
        return data

def task_output(row,user=None):
    latest=row.appointment.incidents.order_by('-pk').first()
    result={'id':row.pk,'appointment_id':row.appointment_id,'contact_id':row.appointment.contact_id,
        'contact_name':row.appointment.contact.name,'reason':row.reason,'priority':row.priority,'due_at':row.due_at,
        'closed_at':row.closed_at,'resolution':row.resolution,'revision':row.revision,
        'overdue':row.closed_at is None and row.due_at<timezone.now(),
        'latest_incident':None if latest is None else {'note':latest.note,'created_at':latest.created_at}}
    if user and user.role=='administrator':result.update(assigned_setter_id=row.setter_id,original_setter_id=row.appointment.setter_id)
    return result

class FollowUpViewSet(viewsets.GenericViewSet):
    serializer_class=CloseInput
    pagination_class=AppointmentPagination
    http_method_names=['get','post','head','options']
    def get_queryset(self):
        if self.request.user.role not in ('setter','administrator'):raise PermissionDenied('Suivi interne uniquement')
        qs=FollowUpTask.objects.select_related('appointment__contact').order_by('closed_at','due_at','pk')
        if self.request.user.role=='setter':qs=qs.filter(setter_id=self.request.user.pk)
        state=self.request.query_params.get('state','open')
        if state not in ('open','closed','all'):raise ValidationError('Filtre invalide')
        if state!='all':qs=qs.filter(closed_at__isnull=state=='open')
        return qs
    def list(self,request):return self.get_paginated_response([task_output(row,request.user) for row in self.paginate_queryset(self.get_queryset())])
    def retrieve(self,request,pk=None):return Response(task_output(self.get_object(),request.user))
    @action(detail=True,methods=['post'])
    def reassign(self,request,pk=None):
        from django.core import signing
        from packages.access.followups import verify_owner
        if request.user.role!='administrator':raise PermissionDenied('Réattribution réservée aux administrateurs')
        row=self.get_object();serializer=TaskOwnerInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
        try:target=verify_owner(data['proof'],request.user.pk,row.pk)
        except (signing.BadSignature,TypeError,ValueError):raise ValidationError('Attestation de setter invalide ou expirée')
        with transaction.atomic():
            if row.closed_at is not None or row.revision!=data['revision']:raise Conflict('Tâche modifiée ou clôturée : actualisez')
            if target['id']==row.setter_id:raise ValidationError('Ce setter est déjà responsable de la tâche')
            before={'setter_id':row.setter_id,'revision':row.revision}
            if not FollowUpTask.objects.filter(pk=row.pk,revision=data['revision'],closed_at__isnull=True).update(
                setter_id=target['id'],revision=F('revision')+1):raise Conflict('Tâche modifiée ou clôturée : actualisez')
            BusinessAudit.objects.create(actor_id=request.user.pk,object_id=row.appointment_id,action='appointment.follow_up_reassigned',
                metadata={'task_id':row.pk,'original_setter_id':row.appointment.setter_id,'before':before,
                    'after':{'setter_id':target['id'],'setter_name':target['name'],'revision':data['revision']+1},'reason':data['reason']})
        row.refresh_from_db();return Response(task_output(row,request.user))
    @action(detail=True,methods=['post'])
    def reopen(self,request,pk=None):
        if request.user.role!='administrator':raise PermissionDenied('Réouverture réservée aux administrateurs')
        row=self.get_object();serializer=TaskPlanInput(data=request.data);serializer.is_valid(raise_exception=True)
        data=serializer.validated_data
        before={'closed_at':row.closed_at.isoformat() if row.closed_at else None,'closed_by_id':row.closed_by_id,
            'resolution':row.resolution,'priority':row.priority,'due_at':row.due_at.isoformat(),
            'revision':row.revision,'policy_revision':row.policy_revision}
        with transaction.atomic():
            if row.revision!=data['revision'] or not FollowUpTask.objects.filter(pk=row.pk,revision=data['revision'],closed_at__isnull=False).update(
                closed_at=None,closed_by_id=None,resolution='',priority=data['priority'],due_at=data['due_at'],
                revision=F('revision')+1):raise Conflict('Tâche modifiée ou déjà ouverte : actualisez')
            BusinessAudit.objects.create(actor_id=request.user.pk,object_id=row.appointment_id,action='appointment.follow_up_reopened',
                metadata={'task_id':row.pk,'before':before,'after':{'closed_at':None,'closed_by_id':None,'resolution':'',
                    'priority':data['priority'],'due_at':data['due_at'].isoformat(),'revision':data['revision']+1},'reason':data['reason']})
        row.refresh_from_db();return Response(task_output(row,request.user))
    @action(detail=True,methods=['post'])
    def plan(self,request,pk=None):
        if request.user.role!='administrator':raise PermissionDenied('Planification réservée aux administrateurs')
        row=self.get_object();serializer=TaskPlanInput(data=request.data);serializer.is_valid(raise_exception=True)
        data=serializer.validated_data
        before={'priority':row.priority,'due_at':row.due_at.isoformat(),'revision':row.revision}
        with transaction.atomic():
            if row.revision!=data['revision'] or not FollowUpTask.objects.filter(pk=row.pk,revision=data['revision'],closed_at__isnull=True).update(
                priority=data['priority'],due_at=data['due_at'],revision=F('revision')+1):raise Conflict('Tâche modifiée ou clôturée : actualisez')
            BusinessAudit.objects.create(actor_id=request.user.pk,object_id=row.appointment_id,action='appointment.follow_up_planned',
                metadata={'task_id':row.pk,'before':before,'after':{'priority':data['priority'],'due_at':data['due_at'].isoformat(),'revision':data['revision']+1},'reason':data['reason']})
        row.refresh_from_db();return Response(task_output(row,request.user))
    @action(detail=True,methods=['get'])
    def history(self,request,pk=None):
        if request.user.role!='administrator':raise PermissionDenied('Historique réservé aux administrateurs')
        row=self.get_object()
        entries=self.paginate_queryset(BusinessAudit.objects.filter(object_id=row.appointment_id,
            action__in=['appointment.notification_read','appointment.follow_up_planned','appointment.follow_up_closed','appointment.follow_up_reopened','appointment.follow_up_reassigned','appointment.follow_up_incident','appointment.incident_reported'],metadata__task_id=row.pk).order_by('-pk'))
        return self.get_paginated_response([{'id':item.pk,'action':item.action,'actor_id':item.actor_id,'created_at':item.created_at,'metadata':item.metadata} for item in entries])
    @action(detail=True,methods=['post'])
    def close(self,request,pk=None):
        original=self.get_object();serializer=CloseInput(data=request.data);serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            writable=FollowUpTask.objects.filter(pk=original.pk,closed_at__isnull=True,revision=serializer.validated_data['revision'])
            if request.user.role=='setter':writable=writable.filter(setter_id=request.user.pk)
            if original.revision!=serializer.validated_data['revision'] or not writable.update(closed_at=timezone.now(),
                closed_by_id=request.user.pk,resolution=serializer.validated_data['resolution'],revision=F('revision')+1):raise Conflict('Tâche modifiée ou déjà clôturée : actualisez')
            BusinessAudit.objects.create(actor_id=request.user.pk,object_id=original.appointment_id,action='appointment.follow_up_closed',
                metadata={'task_id':original.pk,'resolution':serializer.validated_data['resolution']})
        original.refresh_from_db();return Response(task_output(original,request.user))
