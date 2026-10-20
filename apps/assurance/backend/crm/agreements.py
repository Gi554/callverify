"""Administrative register only, no legal status, signatures or automatic access changes."""
import hashlib
import json
from datetime import timedelta
from django.db import transaction,IntegrityError
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied,ValidationError
from rest_framework.response import Response
from .models import Agreement,Contact,BusinessAudit
from .leases import held,Conflict,LEASE_SECONDS

FIELDS=('reference','status','starts_on','ends_on')

def administrator(request):
    if request.user.role!='administrator':raise PermissionDenied('Registre réservé à l’administration Assurance')

class Input(serializers.Serializer):
    token=serializers.UUIDField(write_only=True)
    contact_revision=serializers.IntegerField(min_value=0)
    reason=serializers.CharField(max_length=1000)
    reference=serializers.CharField(max_length=100)
    status=serializers.ChoiceField(choices=['draft','tracking','archived'])
    starts_on=serializers.DateField(allow_null=True,input_formats=['%Y-%m-%d'])
    ends_on=serializers.DateField(allow_null=True,input_formats=['%Y-%m-%d'])
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise ValidationError('Champs non autorisés')
        if data['starts_on'] and data['ends_on'] and data['ends_on']<data['starts_on']:raise ValidationError('La fin doit suivre le début')
        return data
class CreateInput(Input):
    request_id=serializers.UUIDField()
    kind=serializers.ChoiceField(choices=['mandate','contract'])
class EditInput(Input):revision=serializers.IntegerField(min_value=0)

def output(row):
    return {key:getattr(row,key) for key in ('id','kind',*FIELDS,'revision','created_at','updated_at')}
def snapshot(row):
    return {key:(getattr(row,key).isoformat() if getattr(row,key) is not None and key.endswith('_on') else getattr(row,key)) for key in ('kind',*FIELDS,'revision')}
def lock_contact(contact,user,data,check_revision=True):
    now=timezone.now()
    if not held(contact.pk,user,data['token'],now).update(lease_expires_at=now+timedelta(seconds=LEASE_SECONDS)):raise Conflict('Prenez en charge la fiche')
    current=Contact.objects.get(pk=contact.pk)
    if check_revision and current.revision!=data['contact_revision']:raise Conflict('Fiche modifiée : rechargez')
    return current

def audit(user,contact,row,before,reason):
    contact.revision+=1;contact.save(update_fields=['revision','updated_at'])
    BusinessAudit.objects.create(actor_id=user.pk,object_id=contact.pk,action='contact.agreement_changed',metadata={'agreement_id':row.pk,'before':before,'after':snapshot(row),'reason':reason,'contact_revision':contact.revision})

class AgreementMixin:
    @action(detail=True,methods=['get','post'])
    def agreements(self,request,pk=None):
        administrator(request);contact=self.get_object()
        if request.method=='GET':
            qs=Agreement.objects.filter(contact=contact).order_by('-pk')
            response=self.get_paginated_response([output(row) for row in self.paginate_queryset(qs)]);response['Cache-Control']='no-store';return response
        serializer=CreateInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
        canonical={key:(str(data[key]) if data[key] is not None else None) for key in ('kind',*FIELDS,'reason')}
        fingerprint=hashlib.sha256(json.dumps(canonical,sort_keys=True).encode()).hexdigest()
        def replay(row):
            event=BusinessAudit.objects.filter(object_id=contact.pk,action='contact.agreement_changed',metadata__agreement_id=row.pk,metadata__before=None).first()
            if row.contact_id!=contact.pk or row.fingerprint!=fingerprint or not event or event.actor_id!=request.user.pk:raise Conflict('Identifiant de création déjà utilisé')
            return Response({'agreement':output(row),'contact_revision':Contact.objects.get(pk=contact.pk).revision,'replayed':True})
        existing=Agreement.objects.filter(request_id=data['request_id']).first()
        if existing:return replay(existing)
        try:
            with transaction.atomic():
                current=lock_contact(contact,request.user,data,check_revision=False)
                existing=Agreement.objects.filter(request_id=data['request_id']).first()
                if existing:return replay(existing)
                if current.revision!=data['contact_revision']:raise Conflict('Fiche modifiée : rechargez')
                row=Agreement.objects.create(contact=current,request_id=data['request_id'],fingerprint=fingerprint,kind=data['kind'],**{key:data[key] for key in FIELDS})
                audit(request.user,current,row,None,data['reason'])
        except IntegrityError:raise Conflict('Référence ou identifiant déjà utilisé : actualisez avant de reprendre') from None
        return Response({'agreement':output(row),'contact_revision':current.revision,'replayed':False},status=201)

    @action(detail=True,methods=['post'],url_path=r'agreements/(?P<agreement_id>[0-9]+)/edit')
    def edit_agreement(self,request,pk=None,agreement_id=None):
        administrator(request);contact=self.get_object();serializer=EditInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
        try:
            with transaction.atomic():
                current=lock_contact(contact,request.user,data)
                row=get_object_or_404(Agreement,pk=agreement_id,contact=current)
                if row.revision!=data['revision']:raise Conflict('Enregistrement modifié : actualisez')
                before=snapshot(row)
                if any(getattr(row,key)!=data[key] for key in FIELDS):
                    for key in FIELDS:setattr(row,key,data[key])
                    row.revision+=1;row.save(update_fields=[*FIELDS,'revision','updated_at']);audit(request.user,current,row,before,data['reason'])
        except IntegrityError:raise Conflict('Référence déjà utilisée sur ce dossier') from None
        return Response({'agreement':output(row),'contact_revision':current.revision})

    @action(detail=True,methods=['get'],url_path=r'agreements/(?P<agreement_id>[0-9]+)/history')
    def agreement_history(self,request,pk=None,agreement_id=None):
        administrator(request);contact=self.get_object();row=get_object_or_404(Agreement,pk=agreement_id,contact=contact)
        qs=BusinessAudit.objects.filter(object_id=contact.pk,action='contact.agreement_changed',metadata__agreement_id=row.pk).order_by('-pk')
        rows=self.paginate_queryset(qs)
        response=self.get_paginated_response([{'id':event.pk,'created_at':event.created_at,'actor_id':event.actor_id,'before':event.metadata.get('before'),'after':event.metadata.get('after'),'reason':event.metadata.get('reason')} for event in rows]);response['Cache-Control']='no-store';return response
