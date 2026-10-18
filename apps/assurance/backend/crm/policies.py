from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied,ValidationError
from rest_framework.response import Response
from .models import FollowUpPolicy,BusinessAudit
from .leases import Conflict

FIELDS=('initial_hours','reopen_hours','default_priority','revision')

def policy():
    # Safe fallback for fresh databases; saving configuration is admin-only.
    return FollowUpPolicy.objects.filter(pk=1).first() or FollowUpPolicy(pk=1)

def output(row):return {key:getattr(row,key) for key in FIELDS}

class PolicyInput(serializers.Serializer):
    initial_hours=serializers.IntegerField(min_value=1,max_value=720)
    reopen_hours=serializers.IntegerField(min_value=1,max_value=720)
    default_priority=serializers.ChoiceField(choices=['low','normal','high','urgent'])
    revision=serializers.IntegerField(min_value=0)
    reason=serializers.CharField(max_length=1000)
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise ValidationError('Champs non autorisés')
        return data

@api_view(['GET','POST'])
def follow_up_policy(request):
    if request.user.role!='administrator':raise PermissionDenied('Règles réservées aux administrateurs Assurance')
    if request.method=='GET':return Response(output(policy()))
    serializer=PolicyInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
    with transaction.atomic():
        FollowUpPolicy.objects.get_or_create(pk=1)
        row=FollowUpPolicy.objects.get(pk=1);before=output(row)
        if row.revision!=data['revision'] or not FollowUpPolicy.objects.filter(pk=1,revision=data['revision']).update(
            initial_hours=data['initial_hours'],reopen_hours=data['reopen_hours'],default_priority=data['default_priority'],
            revision=data['revision']+1,updated_at=timezone.now()):raise Conflict('Règles modifiées entre-temps : actualisez')
        row.refresh_from_db()
        BusinessAudit.objects.create(actor_id=request.user.pk,object_id=1,action='policy.follow_up_changed',
            metadata={'before':before,'after':output(row),'reason':data['reason']})
    return Response(output(row))

@api_view(['GET'])
def policy_history(request):
    from rest_framework.pagination import PageNumberPagination
    if request.user.role!='administrator':raise PermissionDenied('Historique réservé aux administrateurs Assurance')
    pager=PageNumberPagination();pager.page_size=25
    entries=pager.paginate_queryset(BusinessAudit.objects.filter(action='policy.follow_up_changed').order_by('-pk'),request)
    return pager.get_paginated_response([{'id':row.pk,'actor_id':row.actor_id,'created_at':row.created_at,'metadata':row.metadata} for row in entries])
