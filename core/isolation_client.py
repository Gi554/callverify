from django.db import transaction
from django.db.models import F,Exists,OuterRef
from django.utils import timezone
from rest_framework import serializers,viewsets
from rest_framework.decorators import action,api_view,authentication_classes,permission_classes
from rest_framework.exceptions import PermissionDenied,ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .isolation_work import VisitAuthentication,Pager,Conflict
from .models import IsolationVisit,IsolationVisitResult,IsolationVisitSupplement,Prospect,AuditEvent

OUTCOMES={'completed':'Effectuée','follow_up':'Suivi nécessaire','interested':'Intéressé','not_interested':'Non intéressé','not_performed':'Non effectuée'}

class ResultInput(serializers.Serializer):
    revision=serializers.IntegerField(min_value=0)
    performed=serializers.BooleanField()
    outcome=serializers.ChoiceField(choices=list(OUTCOMES))
    note=serializers.CharField(max_length=3000)
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise ValidationError('Champs non autorisés')
        if data['performed']==(data['outcome']=='not_performed'):raise ValidationError('Résultat commercial incohérent avec la réalisation de la visite')
        return data

def result_output(row):return {'performed':row.performed,'outcome':row.outcome,'note':row.note,'created_at':row.created_at}

class SupplementInput(serializers.Serializer):
    request_id=serializers.UUIDField()
    note=serializers.CharField(max_length=3000)
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise ValidationError('Champs non autorisés')
        return data

def supplement_output(row):return {'id':row.pk,'note':row.note,'created_at':row.created_at,'author_client_id':row.author_client_id}

class ResultMixin:
    @action(detail=True,methods=['get','post'])
    def supplements(self,request,pk=None):
        if request.method=='POST' and request.user.role!='client':raise PermissionDenied('Complément réservé au client de la visite')
        original=self.get_object()
        if request.method=='GET':
            qs=IsolationVisitSupplement.objects.filter(visit=original).order_by('-pk')
            response=self.get_paginated_response([supplement_output(row) for row in self.paginate_queryset(qs)])
            response['Cache-Control']='no-store'
            return response
        serializer=SupplementInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
        def replay(row):
            if (row.visit_id,row.author_client_id,row.note)!=(original.pk,request.user.pk,data['note']):raise Conflict('Identifiant de complément déjà utilisé')
            return Response(supplement_output(row))
        with transaction.atomic():
            if not IsolationVisit.objects.filter(pk=original.pk,client_id=request.user.pk).update(revision=F('revision')):raise PermissionDenied('Visite non autorisée')
            existing=IsolationVisitSupplement.objects.filter(request_id=data['request_id']).first()
            if existing:return replay(existing)
            if not IsolationVisitResult.objects.filter(visit=original).exists():raise Conflict('Renseignez le résultat initial avant un complément')
            row,created=IsolationVisitSupplement.objects.get_or_create(request_id=data['request_id'],defaults={
                'visit':original,'author_client_id':request.user.pk,'note':data['note']})
            if not created:return replay(row)
            AuditEvent.objects.create(action='isolation.visit.supplement_added',object_id=str(original.pk),metadata={
                'actor_portal_id':request.user.pk,'supplement_id':row.pk})
        return Response(supplement_output(row),status=201)
    @action(detail=True,methods=['get','post'])
    def result(self,request,pk=None):
        if request.method=='POST' and request.user.role!='client':raise PermissionDenied('Résultat à renseigner par le client de la visite')
        original=self.get_object()
        if request.method=='GET':
            row=IsolationVisitResult.objects.filter(visit=original).first()
            return Response(None if row is None else result_output(row))
        serializer=ResultInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
        with transaction.atomic():
            IsolationVisit.objects.filter(pk=original.pk,client_id=request.user.pk).update(revision=F('revision'))
            visit=IsolationVisit.objects.get(pk=original.pk)
            if visit.client_id!=request.user.pk:raise PermissionDenied('Visite non autorisée')
            existing=IsolationVisitResult.objects.filter(visit=visit).first()
            if existing:
                if any(getattr(existing,key)!=data[key] for key in ('performed','outcome','note')):raise Conflict('Résultat déjà enregistré ; historique conservé')
                return Response(result_output(existing))
            if visit.revision!=data['revision']:raise Conflict('Visite modifiée : rechargez avant de répondre')
            if visit.status!='scheduled' or visit.ends_at>timezone.now():raise Conflict('Résultat attendu après la fin d’une visite non annulée')
            row=IsolationVisitResult.objects.create(visit=visit,author_client_id=request.user.pk,**{key:data[key] for key in ('performed','outcome','note')})
            visit.revision+=1;visit.save(update_fields=['revision'])
            AuditEvent.objects.create(action='isolation.visit.result_recorded',object_id=str(visit.pk),metadata={
                'actor_portal_id':request.user.pk,'result_id':row.pk,'performed':row.performed,'outcome':row.outcome,'revision':visit.revision})
        return Response(result_output(row),status=201)

class ClientProspectSerializer(serializers.ModelSerializer):
    class Meta:
        model=Prospect
        fields=['id','name','reference','raw_phone']

class ClientProspects(viewsets.ReadOnlyModelViewSet):
    authentication_classes=[VisitAuthentication]
    permission_classes=[IsAuthenticated]
    pagination_class=Pager
    serializer_class=ClientProspectSerializer
    def get_queryset(self):
        if self.request.user.role!='client':raise PermissionDenied('Dossiers du portail client uniquement')
        visits=IsolationVisit.objects.filter(prospect_id=OuterRef('pk'),client_id=self.request.user.pk)
        qs=Prospect.objects.filter(Exists(visits)).order_by('-pk')
        term=self.request.query_params.get('search','').strip()[:250]
        if term:qs=qs.filter(name__icontains=term)
        return qs

@api_view(['GET'])
@authentication_classes([VisitAuthentication])
@permission_classes([IsAuthenticated])
def client_dashboard(request):
    if request.user.role!='client':raise PermissionDenied('Tableau de bord du client uniquement')
    visits=IsolationVisit.objects.filter(client_id=request.user.pk)
    now=timezone.now()
    return Response({'role':'client','prospects':visits.values('prospect_id').distinct().count(),
        'visits':visits.count(),'upcoming':visits.filter(status='scheduled',starts_at__gt=now).count(),
        'results_due':visits.filter(status='scheduled',ends_at__lte=now,result__isnull=True).count(),
        'reported':visits.filter(result__isnull=False).count()})
