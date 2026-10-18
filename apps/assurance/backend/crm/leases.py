"""Short-lived editing leases, fenced by an unguessable acquisition token."""
from datetime import timedelta
from uuid import uuid4
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import APIException,PermissionDenied,ValidationError
from rest_framework.response import Response
from .models import Contact,BusinessAudit

LEASE_SECONDS=180
EDIT_FIELDS=('name','phone','email')

class Conflict(APIException):
    status_code=409
    default_detail='Fiche déjà prise en charge ou verrou expiré. Actualisez la fiche.'

class LeaseInput(serializers.Serializer):
    token=serializers.UUIDField(write_only=True)

class ContactEdit(LeaseInput):
    revision=serializers.IntegerField(min_value=0)
    name=serializers.CharField(required=False,allow_blank=True,max_length=250,trim_whitespace=False)
    phone=serializers.CharField(required=False,max_length=250,trim_whitespace=False)
    email=serializers.CharField(required=False,allow_blank=True,max_length=254,trim_whitespace=False)
    def validate(self,data):
        unknown=set(self.initial_data)-set(self.fields)
        if unknown:raise ValidationError('Champs non modifiables présents')
        if not any(key in data for key in EDIT_FIELDS):raise ValidationError('Aucune modification fournie')
        if 'phone' in data and not data['phone'].strip():raise ValidationError({'phone':'Téléphone requis'})
        return data

def writer(request):
    if request.user.role not in ('administrator','setter'):
        raise PermissionDenied('Modification réservée aux setters et administrateurs')

def held(pk,user,token,now):
    return Contact.objects.filter(pk=pk,lease_owner_id=user.pk,lease_token=token,lease_expires_at__gt=now)

def clear_lease():
    return {'lease_owner_id':None,'lease_token':None,'lease_expires_at':None}

def audit(user,contact,action,metadata=None):
    BusinessAudit.objects.create(actor_id=user.pk,object_id=contact,action=action,metadata=metadata or {})

class ContactLeaseMixin:
    def partial_update(self,request,*args,**kwargs):
        writer(request)
        contact=self.get_object()
        serializer=ContactEdit(data=request.data);serializer.is_valid(raise_exception=True)
        data=serializer.validated_data;now=timezone.now()
        with transaction.atomic():
            # First operation is a conditional write: row lock on PostgreSQL, write
            # reservation on SQLite. Reading the before-image only follows this guard.
            if not held(contact.pk,request.user,data['token'],now).update(lease_expires_at=now+timedelta(seconds=LEASE_SECONDS)):
                raise Conflict()
            contact=Contact.objects.get(pk=contact.pk)
            if contact.revision!=data['revision']:raise Conflict('Version dépassée : rechargez la fiche avant de modifier.')
            before={key:getattr(contact,key) for key in EDIT_FIELDS if key in data and getattr(contact,key)!=data[key]}
            if before:
                for key in before:setattr(contact,key,data[key])
                contact.revision+=1
                contact.save(update_fields=[*before,'revision','updated_at'])
                audit(request.user,contact.pk,'contact.updated',{'before':before,'after':{key:getattr(contact,key) for key in before},'revision':contact.revision})
        return Response(self.get_serializer(contact).data)

    @action(detail=True,methods=['get','post','patch','delete'])
    def lease(self,request,pk=None):
        writer(request);contact=self.get_object();now=timezone.now()
        if request.method=='GET':
            active=bool(contact.lease_expires_at and contact.lease_expires_at>now)
            return Response({'locked':active,'mine':active and contact.lease_owner_id==request.user.pk,
                             'expires_at':contact.lease_expires_at if active else None})
        if request.method=='POST':
            token=uuid4();expires=now+timedelta(seconds=LEASE_SECONDS)
            with transaction.atomic():
                available=Contact.objects.filter(pk=contact.pk).filter(Q(lease_expires_at__isnull=True)|Q(lease_expires_at__lte=now))
                if not available.update(lease_owner_id=request.user.pk,lease_token=token,lease_expires_at=expires):raise Conflict()
                audit(request.user,contact.pk,'contact.claimed')
            return Response({'token':str(token),'expires_at':expires},status=201)
        serializer=LeaseInput(data=request.data);serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            own=held(contact.pk,request.user,serializer.validated_data['token'],now)
            if request.method=='PATCH':
                expires=now+timedelta(seconds=LEASE_SECONDS)
                if not own.update(lease_expires_at=expires):raise Conflict()
                return Response({'expires_at':expires})
            if not own.update(**clear_lease()):raise Conflict()
            audit(request.user,contact.pk,'contact.released')
        return Response(status=204)

    @action(detail=True,methods=['post'])
    def unlock(self,request,pk=None):
        if request.user.role!='administrator':raise PermissionDenied('Déverrouillage réservé à un administrateur')
        contact=self.get_object()
        reason=request.data.get('reason','')
        if not isinstance(reason,str) or not reason.strip() or len(reason)>1000:
            raise ValidationError({'reason':'Motif requis (1 à 1 000 caractères)'})
        with transaction.atomic():
            Contact.objects.filter(pk=contact.pk).update(**clear_lease())
            audit(request.user,contact.pk,'contact.force_unlocked',{'reason':reason.strip()})
        return Response(status=204)

    @action(detail=True,methods=['get'])
    def history(self,request,pk=None):
        if request.user.role!='administrator':raise PermissionDenied('Historique réservé à un administrateur')
        contact=self.get_object()
        qs=BusinessAudit.objects.filter(object_id=contact.pk,action__startswith='contact.').order_by('-pk')
        page=self.paginate_queryset(qs)
        return self.get_paginated_response([{'id':item.pk,'actor_id':item.actor_id,'action':item.action,
            'created_at':item.created_at,'metadata':item.metadata} for item in page])
