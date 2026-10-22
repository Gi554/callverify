from django.db.models import Q
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied,ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from packages.access.isolation_visits import issue_closer
from .models import Membership,AccessAudit


class CloserInput(serializers.Serializer):
    visit_id=serializers.IntegerField(min_value=1)
    closer_id=serializers.IntegerField(min_value=1)
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise ValidationError('Champs non autorisés.')
        return data


@api_view(['GET','POST'])
def closers(request):
    if not Membership.objects.filter(user=request.user,workspace='isolation',active=True,role__in=['administrator','client']).exists():
        raise PermissionDenied('Attribution réservée au client Isolation et à son administration.')
    rows=Membership.objects.filter(workspace='isolation',role='closer',active=True,user__is_active=True).select_related('user')
    if request.method=='GET':
        term=request.query_params.get('search','').strip()[:150]
        if term:rows=rows.filter(Q(user__username__icontains=term)|Q(user__email__icontains=term))
        pager=PageNumberPagination();pager.page_size=25
        return pager.get_paginated_response([{'id':row.user_id,'name':row.user.username} for row in pager.paginate_queryset(rows.order_by('user__username','pk'),request)])
    serializer=CloserInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
    closer=rows.filter(user_id=data['closer_id']).first()
    if not closer:raise ValidationError('Closer Isolation actif requis.')
    AccessAudit.objects.create(user=request.user,workspace='isolation',action='visit.closer_attested',metadata=data)
    return Response({'proof':issue_closer(request.user.pk,data['visit_id'],closer.user_id,closer.user.username),'expires_in':120})
