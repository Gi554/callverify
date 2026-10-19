"""Workspace-scoped administration history with an explicit public field allowlist."""
from datetime import datetime,time,timezone
from uuid import UUID
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from .management_api import require_admin,AccessPagination
from .models import AccessAudit,ROLES

LABELS={'membership.granted':'Accès accordé','membership.updated':'Accès modifié',
    'invitation.created':'Invitation créée','invitation.resend':'Invitation renouvelée',
    'invitation.revoke':'Invitation révoquée','invitation.accepted':'Invitation acceptée'}

class Filters(serializers.Serializer):
    action=serializers.ChoiceField(choices=list(LABELS),required=False)
    actor_id=serializers.IntegerField(min_value=1,max_value=9223372036854775807,required=False)
    start_date=serializers.DateField(input_formats=['%Y-%m-%d'],required=False)
    end_date=serializers.DateField(input_formats=['%Y-%m-%d'],required=False)
    def validate(self,data):
        if data.get('start_date') and data.get('end_date') and data['end_date']<data['start_date']:raise ValidationError('La fin doit suivre le début')
        return data

def details(row):
    # Never serialize the stored metadata wholesale, even for an administrator.
    source=row.metadata if isinstance(row.metadata,dict) else {};result={}
    if row.action.startswith('membership.'):
        subject=source.get('subject')
        if type(subject) is int and subject>0:result['subject_id']=subject
        if row.action=='membership.granted':
            if isinstance(source.get('role'),str) and source['role'] in ROLES[row.workspace]:result['role']=source['role']
            if type(source.get('existing')) is bool:result['existing_account']=source['existing']
        else:
            for phase in ('before','after'):
                state=source.get(phase)
                if not isinstance(state,dict):continue
                clean={}
                if isinstance(state.get('role'),str) and state['role'] in ROLES[row.workspace]:clean['role']=state['role']
                if type(state.get('active')) is bool:clean['active']=state['active']
                result[phase]=clean
    else:
        try:result['invitation_id']=str(UUID(str(source.get('invitation',''))))
        except (ValueError,TypeError,AttributeError):pass
        if isinstance(source.get('role'),str) and source['role'] in ROLES[row.workspace]:result['role']=source['role']
    return result

@api_view(['GET'])
def history(request,workspace):
    require_admin(request.user,workspace)
    if set(request.query_params)-{'action','actor_id','start_date','end_date','page'}:raise ValidationError('Filtre non autorisé')
    serializer=Filters(data=request.query_params);serializer.is_valid(raise_exception=True);data=serializer.validated_data
    qs=AccessAudit.objects.filter(workspace=workspace,action__in=LABELS).select_related('user').order_by('-created_at','-pk')
    if 'action' in data:qs=qs.filter(action=data['action'])
    if 'actor_id' in data:qs=qs.filter(user_id=data['actor_id'])
    if 'start_date' in data:qs=qs.filter(created_at__gte=datetime.combine(data['start_date'],time.min,tzinfo=timezone.utc))
    if 'end_date' in data:qs=qs.filter(created_at__lte=datetime.combine(data['end_date'],time.max,tzinfo=timezone.utc))
    pager=AccessPagination();rows=pager.paginate_queryset(qs,request)
    response=pager.get_paginated_response([{'id':row.pk,'action':row.action,'label':LABELS[row.action],'created_at':row.created_at,
        'actor':None if row.user_id is None else {'id':row.user_id,'username':row.user.username},'details':details(row)} for row in rows])
    response['Cache-Control']='no-store';return response
