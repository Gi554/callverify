"""Central read-only administrative register, no financial fields or provider access."""
from datetime import timedelta,timezone as datetime_timezone
from django.utils import timezone
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
    deadline=serializers.ChoiceField(choices=['','upcoming','overdue'],required=False)
    horizon_days=serializers.ChoiceField(choices=['7','30','90'],default='30')
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
    today=timezone.now().astimezone(datetime_timezone.utc).date();days=int(data['horizon_days'])
    counts=deadline_counts(qs,today,days)
    if data.get('deadline')=='upcoming':qs=qs.filter(status='tracking',ends_on__gte=today,ends_on__lte=today+timedelta(days=days)).order_by('ends_on','pk')
    elif data.get('deadline')=='overdue':qs=qs.filter(status='tracking',ends_on__lt=today).order_by('ends_on','pk')
    pager=PageNumberPagination();pager.page_size=25;rows=pager.paginate_queryset(qs,request)
    response=pager.get_paginated_response([{**output(row),'contact':{'id':row.contact_id,'name':row.contact.name},'document_count':row.document_count,'deadline_state':deadline_state(row,today,days),'days_to_end':(row.ends_on-today).days if row.ends_on else None} for row in rows])
    response.data['deadlines']={**counts,'as_of':today,'timezone':'UTC','horizon_days':days}
    response['Cache-Control']='no-store';return response


def deadline_counts(qs,today,days):
    return qs.filter(status='tracking').aggregate(overdue=Count('pk',filter=Q(ends_on__lt=today),distinct=True),upcoming=Count('pk',filter=Q(ends_on__gte=today,ends_on__lte=today+timedelta(days=days)),distinct=True),undated=Count('pk',filter=Q(ends_on__isnull=True),distinct=True))

def deadline_state(row,today,days):
    if row.status!='tracking':return 'not_tracked'
    if row.ends_on is None:return 'undated'
    if row.ends_on<today:return 'overdue'
    if row.ends_on<=today+timedelta(days=days):return 'upcoming'
    return 'later'

class DeadlineWindow(serializers.Serializer):
    horizon_days=serializers.ChoiceField(choices=['7','30','90'],default='30')
    def validate(self,data):
        if set(self.initial_data)-set(self.fields) or any(len(self.initial_data.getlist(key))!=1 for key in self.initial_data):raise serializers.ValidationError('Paramètres invalides')
        return data

@api_view(['GET'])
def deadlines(request):
    administrator(request);serializer=DeadlineWindow(data=request.query_params);serializer.is_valid(raise_exception=True)
    days=int(serializer.validated_data['horizon_days']);today=timezone.now().astimezone(datetime_timezone.utc).date()
    response=Response({**deadline_counts(Agreement.objects.all(),today,days),'as_of':today,'timezone':'UTC','horizon_days':days})
    response['Cache-Control']='no-store';return response
