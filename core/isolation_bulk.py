"""Bounded, atomic and idempotent admin assignment batches."""
import hashlib
import json
from django.core import signing
from django.db import transaction
from django.db.models import F
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError,PermissionDenied
from rest_framework.response import Response
from packages.access.isolation import verify_owner
from .models import Prospect,AuditEvent,IsolationAssignmentBatch

class Item(serializers.Serializer):
    id=serializers.IntegerField(min_value=1)
    revision=serializers.IntegerField(min_value=0)
    proof=serializers.CharField(max_length=3000,required=False)
    def to_internal_value(self,data):
        if isinstance(data,dict) and set(data)-set(self.fields):raise ValidationError('Champs non autorisés')
        return super().to_internal_value(data)

class BatchInput(serializers.Serializer):
    request_id=serializers.UUIDField()
    reason=serializers.CharField(max_length=1000)
    setter_id=serializers.IntegerField(min_value=1,allow_null=True)
    items=Item(many=True,min_length=1,max_length=25)
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise ValidationError('Champs non autorisés')
        ids=[item['id'] for item in data['items']]
        if len(ids)!=len(set(ids)):raise ValidationError('Un prospect ne peut figurer deux fois')
        if data['setter_id'] is None and any('proof' in item for item in data['items']):raise ValidationError('Aucune attestation pour un retrait')
        return data

class BulkAssignmentMixin:
    @action(detail=False,methods=['post'],url_path='bulk-assign')
    def bulk_assign(self,request):
        from .isolation_work import Conflict
        if request.user.role!='administrator':raise PermissionDenied('Affectation en lot réservée aux administrateurs Isolation')
        serializer=BatchInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
        items=sorted(data['items'],key=lambda item:item['id'])
        canonical={'setter_id':data['setter_id'],'reason':data['reason'],'items':[{'id':item['id'],'revision':item['revision']} for item in items]}
        fingerprint=hashlib.sha256(json.dumps(canonical,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        def replay(batch):
            if (batch.actor_portal_id,batch.fingerprint)!=(request.user.pk,fingerprint):raise Conflict('Identifiant de lot déjà utilisé')
            return Response(batch.result)
        existing=IsolationAssignmentBatch.objects.filter(request_id=data['request_id']).first()
        if existing:return replay(existing)
        targets={}
        for item in items:
            if data['setter_id'] is None:targets[item['id']]=(None,'');continue
            try:claims=verify_owner(item.get('proof',''),request.user.pk,item['id'])
            except (signing.BadSignature,ValueError,TypeError):raise ValidationError(f"Attestation invalide ou expirée pour le prospect {item['id']}")
            if claims['setter']!=data['setter_id']:raise ValidationError('Le setter attesté diffère du destinataire du lot')
            targets[item['id']]=(claims['setter'],claims['name'])
        with transaction.atomic():
            batch,created=IsolationAssignmentBatch.objects.get_or_create(request_id=data['request_id'],defaults={'actor_portal_id':request.user.pk,'fingerprint':fingerprint})
            if not created:return replay(batch)
            result=[]
            for item in items:
                # Conditional write locks each row in ascending order, shared with single assignments and activities.
                writable=Prospect.objects.filter(pk=item['id'],assignment_revision=item['revision'])
                if not writable.update(assignment_revision=F('assignment_revision')+1):raise Conflict(f"Prospect {item['id']} modifié ou absent : aucun changement du lot")
                row=Prospect.objects.get(pk=item['id']);target_id,target_name=targets[row.pk]
                if row.assigned_setter_id==target_id:raise ValidationError(f'Prospect {row.pk} déjà affecté à cette cible : aucun changement du lot')
                before={'setter_id':row.assigned_setter_id,'setter_name':row.assigned_setter_name,'revision':item['revision']}
                row.assigned_setter_id=target_id;row.assigned_setter_name=target_name;row.save(update_fields=['assigned_setter_id','assigned_setter_name'])
                AuditEvent.objects.create(action='isolation.prospect.assigned',object_id=str(row.pk),metadata={'actor_portal_id':request.user.pk,'batch':str(batch.request_id),
                    'before':before,'after':{'setter_id':target_id,'setter_name':target_name,'revision':row.assignment_revision},'reason':data['reason']})
                result.append({'id':row.pk,'revision':row.assignment_revision})
            batch.result={'request_id':str(batch.request_id),'count':len(result),'items':result};batch.save(update_fields=['result'])
        return Response(batch.result,status=201)
