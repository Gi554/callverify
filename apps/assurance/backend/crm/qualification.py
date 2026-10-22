"""Explicit Assurance fields. Advisors read booking snapshots, never live internal drafts."""
from copy import deepcopy
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from .agreements import lock_contact
from .models import Appointment,BusinessAudit

PROFESSIONS={'full_time':'Salarié à temps plein','part_time':'Salarié à temps partiel','self_employed':'Travailleur autonome','retired':'Retraité','other':'Autre'}
MARITAL={'married':'Marié','single':'Célibataire / non marié','common_law':'Conjoint de fait','other':'Autre / préfère ne pas répondre'}
INSURANCES={'life':'Assurance vie','disability':'Assurance invalidité','critical_illness':'Assurance maladies graves','group':'Assurances collectives','none_known':'Aucune assurance connue'}
FIELDS=[{'key':'age','label':'Âge','type':'number','min':0,'max':120},
    {'key':'profession','label':'Profession','type':'choice','choices':PROFESSIONS},
    {'key':'marital_status','label':'Situation matrimoniale','type':'choice','choices':MARITAL},
    *[{'key':key,'label':label,'type':'boolean'} for key,label in [('has_children','A des enfants'),('homeowner','Est propriétaire'),('smoker','Statut de fumeur'),('has_advisor','Possède actuellement un conseiller en sécurité financière')]],
    {'key':'insurances','label':'Types d’assurances détenues','type':'multiple','choices':INSURANCES},
    {'key':'additional_notes','label':'Notes complémentaires','type':'text'},
    {'key':'advisor_notes','label':'Notes utiles pour le conseiller','type':'text'}]

class Qualification(serializers.Serializer):
    age=serializers.IntegerField(min_value=0,max_value=120,allow_null=True,default=None)
    profession=serializers.ChoiceField(choices=PROFESSIONS,allow_blank=True,default='')
    marital_status=serializers.ChoiceField(choices=MARITAL,allow_blank=True,default='')
    has_children=serializers.BooleanField(allow_null=True,default=None)
    homeowner=serializers.BooleanField(allow_null=True,default=None)
    smoker=serializers.BooleanField(allow_null=True,default=None)
    has_advisor=serializers.BooleanField(allow_null=True,default=None)
    insurances=serializers.ListField(child=serializers.ChoiceField(choices=INSURANCES),max_length=5,default=list)
    additional_notes=serializers.CharField(max_length=3000,allow_blank=True,default='')
    advisor_notes=serializers.CharField(max_length=3000,allow_blank=True,default='')
    def to_internal_value(self,data):
        if isinstance(data,dict) and set(data)-set(self.fields):raise serializers.ValidationError('Champs de qualification inconnus.')
        return super().to_internal_value(data)
    def validate(self,data):
        if len(data['insurances'])!=len(set(data['insurances'])):raise serializers.ValidationError('Sélectionnez chaque assurance une seule fois.')
        if 'none_known' in data['insurances'] and len(data['insurances'])>1:raise serializers.ValidationError('Aucune assurance connue ne peut pas être combinée avec une autre assurance.')
        return data

class Input(serializers.Serializer):
    token=serializers.UUIDField(write_only=True)
    contact_revision=serializers.IntegerField(min_value=0)
    qualification=Qualification()
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise serializers.ValidationError('Champs non autorisés.')
        return data

def snapshot(contact):
    return {'version':1,'fields':deepcopy(FIELDS),'contact':{'name':contact.name,'phone':contact.phone,'email':contact.email},
        'qualification':deepcopy(contact.assurance_qualification),'contact_revision':contact.revision,'captured_at':timezone.now().isoformat()}

class QualificationMixin:
    @action(detail=True,methods=['get','post'],url_path='qualification')
    def assurance_qualification(self,request,pk=None):
        contact=self.get_object()
        if request.user.role=='advisor':
            if request.method!='GET':raise PermissionDenied('Qualification transmise en lecture seule.')
            row=Appointment.objects.filter(contact=contact,advisor_id=request.user.pk).exclude(qualification_snapshot={}).order_by('-created_at','-pk').first()
            response=Response({'fields':FIELDS,'source':'appointment_snapshot','snapshot':row.qualification_snapshot if row else None,'appointment_id':row.pk if row else None})
        elif request.user.role in ('setter','administrator'):
            if request.method=='POST':
                serializer=Input(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
                with transaction.atomic():
                    contact=lock_contact(contact,request.user,data)
                    if contact.assurance_qualification!=data['qualification']:
                        before=deepcopy(contact.assurance_qualification);contact.assurance_qualification=data['qualification'];contact.revision+=1
                        contact.save(update_fields=['assurance_qualification','revision','updated_at'])
                        BusinessAudit.objects.create(actor_id=request.user.pk,object_id=contact.pk,action='contact.assurance_qualification_updated',
                            metadata={'before':before,'after':data['qualification'],'revision':contact.revision})
            response=Response({'fields':FIELDS,'qualification':contact.assurance_qualification,'contact_revision':contact.revision,'source':'contact'})
        else:raise PermissionDenied('Espace Assurance requis.')
        response['Cache-Control']='no-store';return response
