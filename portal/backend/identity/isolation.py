from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django.db.models import Q
from .management_api import require_admin
from .models import Membership,AccessAudit
from packages.access.isolation import issue_owner

class AssignmentInput(serializers.Serializer):
    setter_id=serializers.IntegerField(min_value=1)
    prospect_id=serializers.IntegerField(min_value=1)
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise ValidationError('Champs non autorisés')
        return data

@api_view(['GET','POST'])
def setters(request):
    require_admin(request.user,'isolation')
    qs=Membership.objects.filter(workspace='isolation',role='setter',active=True,user__is_active=True).select_related('user')
    if request.method=='GET':
        term=request.query_params.get('search','').strip()[:150]
        if term:qs=qs.filter(Q(user__username__icontains=term)|Q(user__email__icontains=term))
        pager=PageNumberPagination();pager.page_size=25
        rows=pager.paginate_queryset(qs.order_by('user__username','pk'),request)
        return pager.get_paginated_response([{'id':row.user_id,'name':row.user.username} for row in rows])
    serializer=AssignmentInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
    target=qs.filter(user_id=data['setter_id']).first()
    if target is None:raise ValidationError('Setter Isolation actif requis')
    AccessAudit.objects.create(user=request.user,workspace='isolation',action='prospect.owner_attested',metadata=data)
    return Response({'proof':issue_owner(request.user.pk,data['prospect_id'],target.user_id,target.user.username),'expires_in':120})
