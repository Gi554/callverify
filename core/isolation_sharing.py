"""Explicit publication of immutable observations to a visit's client."""
from django.db import transaction
from django.db.models import Exists,OuterRef,F
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied,ValidationError
from rest_framework.response import Response
from .models import Prospect,ProspectActivity,ProspectActivityShare,AuditEvent
from .isolation_activity import output


class SharingInput(serializers.Serializer):
    activity_id=serializers.IntegerField(min_value=1)
    revision=serializers.IntegerField(min_value=0)
    visible=serializers.BooleanField()
    reason=serializers.CharField(max_length=1000)
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise ValidationError('Champs non autorisés')
        return data


class SharingMixin:
    @action(detail=True,methods=['get','post'])
    def activities(self,request,pk=None):
        from .isolation_work import Conflict
        if request.method=='POST' and request.user.role=='client':raise PermissionDenied('Publication réservée au responsable ou à l’administration Isolation')
        visit=self.get_object()
        if request.method=='GET':
            shares=ProspectActivityShare.objects.filter(activity_id=OuterRef('pk'),client_id=visit.client_id,visible=True)
            qs=ProspectActivity.objects.filter(prospect_id=visit.prospect_id,kind__in=['note','qualification']).annotate(shared=Exists(shares)).order_by('-pk')
            if request.user.role=='client':qs=qs.filter(shared=True)
            response=self.get_paginated_response([{**output(row),'shared':row.shared} for row in self.paginate_queryset(qs)])
            response['Cache-Control']='no-store'
            return response
        serializer=SharingInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
        with transaction.atomic():
            # Same CAS/lock as assignment and new observations: former owners cannot publish.
            writable=Prospect.objects.filter(pk=visit.prospect_id,assignment_revision=data['revision'])
            if request.user.role=='setter':writable=writable.filter(assigned_setter_id=request.user.pk)
            if not writable.update(assignment_revision=F('assignment_revision')+1):raise Conflict('Prospect modifié ou réattribué : rechargez')
            activity=ProspectActivity.objects.filter(pk=data['activity_id'],prospect_id=visit.prospect_id,kind__in=['note','qualification']).first()
            if activity is None:raise ValidationError('Observation absente de ce dossier')
            share,_=ProspectActivityShare.objects.get_or_create(activity=activity,client_id=visit.client_id)
            if share.visible==data['visible']:raise Conflict('Visibilité déjà identique : rechargez')
            share.visible=data['visible'];share.save(update_fields=['visible','updated_at'])
            AuditEvent.objects.create(action='isolation.prospect.activity_visibility_changed',object_id=str(visit.prospect_id),metadata={
                'actor_portal_id':request.user.pk,'activity_id':activity.pk,'client_id':visit.client_id,'visit_id':visit.pk,
                'before':{'visible':not share.visible},'after':{'visible':share.visible},'reason':data['reason'],'revision':data['revision']+1})
        response=Response({'activity_id':activity.pk,'shared':share.visible,'revision':data['revision']+1})
        response['Cache-Control']='no-store'
        return response
