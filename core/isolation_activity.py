"""Append-only commercial observations, independent of technical phone results."""
import hashlib
import json
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from .models import Prospect,ProspectActivity,AuditEvent

STATUSES={'to_contact':'À contacter','in_progress':'En cours','callback':'À rappeler','interested':'Intéressé',
    'not_interested':'Non intéressé','unreachable':'Non joint'}

class ActivityInput(serializers.Serializer):
    request_id=serializers.UUIDField()
    revision=serializers.IntegerField(min_value=0)
    kind=serializers.ChoiceField(choices=['note','qualification'])
    body=serializers.CharField(max_length=3000)
    status=serializers.ChoiceField(choices=list(STATUSES),required=False)
    callback_at=serializers.DateTimeField(required=False,allow_null=True)
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise ValidationError('Champs non autorisés')
        if data['kind']=='note':
            if 'status' in data or 'callback_at' in data:raise ValidationError('Une note ne modifie pas la qualification')
        else:
            if 'status' not in data:raise ValidationError('Résultat commercial requis')
            if data['status']=='callback':
                if not data.get('callback_at'):raise ValidationError('Date de rappel requise')
            elif data.get('callback_at') is not None:raise ValidationError('Date réservée au statut À rappeler')
            if data.get('callback_at'):
                raw=parse_datetime(str(self.initial_data['callback_at']))
                if raw is None or timezone.is_naive(raw):raise ValidationError('Date de rappel avec décalage ISO 8601 explicite requise')
        return data

def output(row):
    return {'id':row.pk,'kind':row.kind,'body':row.body,'changes':row.changes,
        'author_portal_id':row.author_portal_id,'author_role':row.author_role,'created_at':row.created_at}

class ActivityMixin:
    @action(detail=True,methods=['get','post'])
    def activities(self,request,pk=None):
        from .isolation_work import Conflict
        prospect=self.get_object();user=request.user
        if request.method=='GET':
            qs=ProspectActivity.objects.filter(prospect=prospect).order_by('-pk')
            response=self.get_paginated_response([output(row) for row in self.paginate_queryset(qs)])
            response['Cache-Control']='no-store'
            return response
        serializer=ActivityInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
        canonical={key:(value.isoformat() if key=='callback_at' and value else value) for key,value in data.items() if key not in ('request_id','revision')}
        fingerprint=hashlib.sha256(json.dumps(canonical,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        def replay(row):
            if (row.prospect_id,row.author_portal_id,row.author_role,row.fingerprint)!=(prospect.pk,user.pk,user.role,fingerprint):raise Conflict('Identifiant d’activité déjà utilisé')
            return Response(output(row))
        existing=ProspectActivity.objects.filter(request_id=data['request_id']).first()
        if existing:return replay(existing)
        with transaction.atomic():
            writable=Prospect.objects.filter(pk=prospect.pk,assignment_revision=data['revision'])
            if user.role=='setter':writable=writable.filter(assigned_setter_id=user.pk)
            if prospect.assignment_revision!=data['revision'] or not writable.update(assignment_revision=F('assignment_revision')+1):raise Conflict('Prospect modifié ou réattribué : rechargez')
            row=Prospect.objects.get(pk=prospect.pk)
            changes={}
            if data['kind']=='qualification':
                callback=data.get('callback_at')
                if callback and callback<=timezone.now():raise ValidationError('Le rappel doit être dans le futur')
                before={'status':row.commercial_status,'callback_at':row.callback_at.isoformat() if row.callback_at else None}
                row.commercial_status=data['status'];row.callback_at=callback
                row.save(update_fields=['commercial_status','callback_at'])
                changes={'before':before,'after':{'status':row.commercial_status,'callback_at':callback.isoformat() if callback else None}}
            activity,created=ProspectActivity.objects.get_or_create(request_id=data['request_id'],defaults={
                'prospect':row,'author_portal_id':user.pk,'author_role':user.role,'fingerprint':fingerprint,
                'kind':data['kind'],'body':data['body'],'changes':changes})
            if not created:
                # A concurrent replay may reach this branch on a different prospect;
                # roll back any tentative update before returning the existing event.
                transaction.set_rollback(True)
                return replay(activity)
            if data['kind']=='qualification' and data['status']=='callback':
                from .models import IsolationFollowUp
                IsolationFollowUp.objects.create(prospect=row,request_id=data['request_id'],fingerprint=fingerprint,
                    created_by_id=user.pk,note=data['body'],due_at=data['callback_at'])
            AuditEvent.objects.create(action='isolation.prospect.activity_added',object_id=str(row.pk),metadata={
                'actor_portal_id':user.pk,'activity_id':activity.pk,'kind':activity.kind,'revision':row.assignment_revision})
        return Response(output(activity),status=201)
