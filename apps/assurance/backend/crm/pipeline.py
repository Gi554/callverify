"""Explicit commercial stages, independent from appointment and contract evidence."""
from datetime import timedelta
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view,action
from rest_framework.exceptions import PermissionDenied,ValidationError
from rest_framework.response import Response
from .models import ContactPipeline,Contact,BusinessAudit
from .leases import writer,held,Conflict,LEASE_SECONDS

DEFAULT_STAGES=[{'key':key,'label':label,'active':True} for key,label in [
    ('to_contact','À contacter'),('in_progress','En cours'),('callback','À rappeler'),
    ('interested','Intéressé'),('appointment_booked','RDV réservé'),('appointment_done','RDV effectué'),
    ('incident','Incident'),('follow_up','Suivi'),('mandate','Mandat'),('contract','Contrat'),('closed','Clôturé')]]

def pipeline():return ContactPipeline.objects.filter(pk=1).first() or ContactPipeline(pk=1,stages=DEFAULT_STAGES)
def output(row):return {'stages':row.stages,'revision':row.revision}

class Stage(serializers.Serializer):
    key=serializers.RegexField(r'^[a-z][a-z0-9_]{0,39}$')
    label=serializers.CharField(max_length=100)
    active=serializers.BooleanField()
    def to_internal_value(self,data):
        if isinstance(data,dict) and set(data)-set(self.fields):raise ValidationError('Propriété de statut inconnue')
        return super().to_internal_value(data)

class PipelineInput(serializers.Serializer):
    revision=serializers.IntegerField(min_value=0)
    reason=serializers.CharField(max_length=1000)
    stages=Stage(many=True)
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise ValidationError('Champs non autorisés')
        stages=data['stages'];keys={s['key'] for s in stages}
        if not 1<=len(stages)<=30 or len(keys)!=len(stages):raise ValidationError('De 1 à 30 clés distinctes requises')
        if not any(s['key']=='to_contact' and s['active'] for s in stages):raise ValidationError('Le statut initial to_contact doit rester actif pour les imports')
        return data

@api_view(['GET','POST'])
def configuration(request):
    if request.method=='GET':return Response(output(pipeline()))
    if request.user.role!='administrator':raise PermissionDenied('Configuration réservée à l’administration')
    serializer=PipelineInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
    with transaction.atomic():
        ContactPipeline.objects.get_or_create(pk=1,defaults={'stages':DEFAULT_STAGES})
        ContactPipeline.objects.filter(pk=1).update(revision=F('revision'))
        row=ContactPipeline.objects.get(pk=1)
        if row.revision!=data['revision']:raise Conflict('Pipeline modifié : rechargez')
        if {s['key'] for s in row.stages}-{s['key'] for s in data['stages']}:raise ValidationError('Conservez les clés existantes ; archivez les statuts inutilisés')
        before=output(row)
        row.stages=data['stages'];row.revision+=1;row.save(update_fields=['stages','revision'])
        BusinessAudit.objects.create(actor_id=request.user.pk,object_id=1,action='schema.pipeline_changed',
            metadata={'before':before,'after':output(row),'reason':data['reason']})
    return Response(output(row))

class StatusInput(serializers.Serializer):
    token=serializers.UUIDField()
    revision=serializers.IntegerField(min_value=0)
    pipeline_revision=serializers.IntegerField(min_value=0)
    status=serializers.CharField(max_length=40)
    reason=serializers.CharField(max_length=1000)
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise ValidationError('Champs non autorisés')
        return data

class ContactPipelineMixin:
    @action(detail=True,methods=['post'],url_path='commercial-status')
    def commercial_status(self,request,pk=None):
        writer(request);contact=self.get_object()
        serializer=StatusInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
        with transaction.atomic():
            now=timezone.now()
            if not held(contact.pk,request.user,data['token'],now).update(lease_expires_at=now+timedelta(seconds=LEASE_SECONDS)):raise Conflict('Prise en charge requise')
            ContactPipeline.objects.get_or_create(pk=1,defaults={'stages':DEFAULT_STAGES})
            ContactPipeline.objects.filter(pk=1).update(revision=F('revision'))
            rules=ContactPipeline.objects.get(pk=1)
            if rules.revision!=data['pipeline_revision']:raise Conflict('Pipeline modifié : rechargez')
            contact=Contact.objects.get(pk=contact.pk)
            if contact.revision!=data['revision']:raise Conflict('Fiche modifiée : rechargez')
            stage=next((s for s in rules.stages if s['key']==data['status'] and s['active']),None)
            if stage is None:raise ValidationError({'status':'Statut inconnu ou archivé'})
            if contact.status!=stage['key']:
                before=contact.status;contact.status=stage['key'];contact.revision+=1
                contact.save(update_fields=['status','revision','updated_at'])
                BusinessAudit.objects.create(actor_id=request.user.pk,object_id=contact.pk,action='contact.status_changed',
                    metadata={'before':before,'after':contact.status,'label':stage['label'],'reason':data['reason'],
                        'pipeline_revision':rules.revision,'revision':contact.revision})
        return Response(self.get_serializer(contact).data)
