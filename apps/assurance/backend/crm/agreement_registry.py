"""Central read-only administrative register, no financial fields or provider access."""
from django.db.models import Q,Count
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from .models import Agreement
from .agreements import administrator,output

class Filters(serializers.Serializer):
    search=serializers.CharField(max_length=250,required=False,allow_blank=True)
    kind=serializers.ChoiceField(choices=['','mandate','contract'],required=False)
    status=serializers.ChoiceField(choices=['','draft','tracking','archived'],required=False)
    starts_from=serializers.DateField(required=False,input_formats=['%Y-%m-%d'])
    starts_to=serializers.DateField(required=False,input_formats=['%Y-%m-%d'])
    ends_from=serializers.DateField(required=False,input_formats=['%Y-%m-%d'])
    ends_to=serializers.DateField(required=False,input_formats=['%Y-%m-%d'])
    page=serializers.IntegerField(min_value=1,required=False)
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise serializers.ValidationError('Filtre inconnu')
        if any(len(self.initial_data.getlist(key))!=1 for key in self.initial_data):raise serializers.ValidationError('Filtre répété')
        for prefix in ('starts','ends'):
            first=data.get(prefix+'_from');last=data.get(prefix+'_to')
            if first and last and first>last:raise serializers.ValidationError('Bornes de dates inversées')
        return data

@api_view(['GET'])
def registry(request):
    administrator(request);serializer=Filters(data=request.query_params);serializer.is_valid(raise_exception=True);data=serializer.validated_data
    qs=Agreement.objects.select_related('contact').annotate(document_count=Count('document_links',filter=Q(document_links__active=True))).order_by('-updated_at','-pk')
    if data.get('search'):qs=qs.filter(Q(reference__icontains=data['search'])|Q(contact__name__icontains=data['search']))
    for key in ('kind','status'):
        if data.get(key):qs=qs.filter(**{key:data[key]})
    for prefix,field in (('starts','starts_on'),('ends','ends_on')):
        for suffix,operator in (('from','gte'),('to','lte')):
            key=prefix+'_'+suffix
            if key in data:qs=qs.filter(**{field+'__'+operator:data[key]})
    pager=PageNumberPagination();pager.page_size=25;rows=pager.paginate_queryset(qs,request)
    response=pager.get_paginated_response([{**output(row),'contact':{'id':row.contact_id,'name':row.contact.name},'document_count':row.document_count} for row in rows])
    response['Cache-Control']='no-store';return response
