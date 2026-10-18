"""Active central participants, only visible to Assurance administrators."""
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django.db.models import Q
from .models import Membership,AccessAudit
from .management_api import require_admin
from packages.access.assignments import issue_assignment

class PairInput(serializers.Serializer):
    setter_id=serializers.IntegerField(min_value=1)
    advisor_id=serializers.IntegerField(min_value=1)

@api_view(['GET','POST'])
def participants(request):
    require_admin(request.user,'assurance')
    active=Membership.objects.filter(workspace='assurance',active=True,user__is_active=True).select_related('user')
    if request.method=='GET':
        role=request.query_params.get('role','')
        if role not in ('setter','advisor'):raise ValidationError({'role':'Choisir setter ou advisor'})
        qs=active.filter(role=role).order_by('user__username','pk')
        term=request.query_params.get('search','').strip()[:150]
        if term:qs=qs.filter(Q(user__username__icontains=term)|Q(user__email__icontains=term))
        pager=PageNumberPagination();pager.page_size=25
        rows=pager.paginate_queryset(qs,request)
        return pager.get_paginated_response([{'id':row.user_id,'name':row.user.username,'role':row.role} for row in rows])
    data=PairInput(data=request.data);data.is_valid(raise_exception=True)
    pair={role:active.filter(role=role,user_id=data.validated_data[role+'_id']).first() for role in ('setter','advisor')}
    if not all(pair.values()):raise ValidationError('Sélection indisponible : les deux comptes doivent être actifs avec le rôle Assurance attendu')
    setter,advisor=pair['setter'],pair['advisor']
    AccessAudit.objects.create(user=request.user,action='assignment.attested',workspace='assurance',
        metadata={'setter_id':setter.user_id,'advisor_id':advisor.user_id})
    return Response({'proof':issue_assignment(request.user.pk,setter.user_id,setter.user.username,advisor.user_id,advisor.user.username),'expires_in':120})
