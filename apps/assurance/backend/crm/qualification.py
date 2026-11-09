"""Explicit Assurance fields. Advisors read booking snapshots, never live internal drafts."""

from copy import deepcopy
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from .agreements import lock_contact
from .models import Appointment, BusinessAudit

PROFESSIONS = {
    'full_time': 'Salarié à temps plein',
    'part_time': 'Salarié à temps partiel',
    'self_employed': 'Travailleur autonome',
    'retired': 'Retraité',
    'other': 'Autre',
}
MARITAL = {
    'married': 'Marié',
    'single': 'Célibataire / non marié',
    'common_law': 'Conjoint de fait',
    'other': 'Autre / préfère ne pas répondre',
}
FIELDS = [
    {'key': 'age', 'label': 'Âge', 'type': 'number', 'min': 0, 'max': 120},
    {'key': 'profession', 'label': 'Profession', 'type': 'choice', 'choices': PROFESSIONS},
    {
        'key': 'marital_status',
        'label': 'Situation matrimoniale',
        'type': 'choice',
        'choices': MARITAL,
    },
    *[
        {'key': key, 'label': label, 'type': 'boolean'}
        for key, label in [
            ('has_children', 'A des enfants'),
            ('homeowner', 'Est propriétaire'),
            ('has_investments', 'A des placements ou de l’épargne en cours ?'),
            ('has_advisor', 'Possède actuellement un conseiller en sécurité financière'),
        ]
    ],
    {'key': 'additional_notes', 'label': 'Notes complémentaires', 'type': 'text'},
    {'key': 'advisor_notes', 'label': 'Notes utiles pour le conseiller', 'type': 'text'},
]


class Qualification(serializers.Serializer):
    age = serializers.IntegerField(min_value=0, max_value=120, allow_null=True, default=None)
    profession = serializers.ChoiceField(choices=PROFESSIONS, allow_blank=True, default='')
    marital_status = serializers.ChoiceField(choices=MARITAL, allow_blank=True, default='')
    has_children = serializers.BooleanField(allow_null=True, default=None)
    homeowner = serializers.BooleanField(allow_null=True, default=None)
    has_investments = serializers.BooleanField(allow_null=True, default=None)
    has_advisor = serializers.BooleanField(allow_null=True, default=None)
    additional_notes = serializers.CharField(max_length=3000, allow_blank=True, default='')
    advisor_notes = serializers.CharField(max_length=3000, allow_blank=True, default='')

    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise serializers.ValidationError('Champs de qualification inconnus.')
        return super().to_internal_value(data)


class Input(serializers.Serializer):
    token = serializers.UUIDField(write_only=True)
    contact_revision = serializers.IntegerField(min_value=0)
    qualification = Qualification()

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise serializers.ValidationError('Champs non autorisés.')
        return data


def visible_qualification(values):
    return {key: value for key, value in values.items() if key != 'insurances'}


def visible_snapshot(value):
    result = deepcopy(value)
    if 'fields' in result:
        result['fields'] = [field for field in result['fields'] if field['key'] != 'insurances']
    if 'qualification' in result:
        result['qualification'] = visible_qualification(result['qualification'])
    return result


def snapshot(contact):
    return {
        'version': 1,
        'fields': deepcopy(FIELDS),
        'contact': {'name': contact.name, 'phone': contact.phone, 'email': contact.email},
        'qualification': visible_qualification(contact.assurance_qualification),
        'contact_revision': contact.revision,
        'captured_at': timezone.now().isoformat(),
    }


class QualificationMixin:
    @action(detail=True, methods=['get', 'post'], url_path='qualification')
    def assurance_qualification(self, request, pk=None):
        contact = self.get_object()
        if request.user.role == 'advisor':
            if request.method != 'GET':
                raise PermissionDenied('Qualification transmise en lecture seule.')
            row = (
                Appointment.objects.filter(contact=contact, advisor_id=request.user.pk)
                .exclude(qualification_snapshot={})
                .order_by('-created_at', '-pk')
                .first()
            )
            response = Response(
                {
                    'fields': FIELDS,
                    'source': 'appointment_snapshot',
                    'snapshot': visible_snapshot(row.qualification_snapshot) if row else None,
                    'appointment_id': row.pk if row else None,
                }
            )
        elif request.user.role in ('setter', 'administrator'):
            if request.method == 'POST':
                serializer = Input(data=request.data)
                serializer.is_valid(raise_exception=True)
                data = serializer.validated_data
                with transaction.atomic():
                    contact = lock_contact(contact, request.user, data)
                    if contact.assurance_qualification != data['qualification']:
                        before = deepcopy(contact.assurance_qualification)
                        contact.assurance_qualification = data['qualification']
                        contact.revision += 1
                        contact.save(
                            update_fields=['assurance_qualification', 'revision', 'updated_at']
                        )
                        BusinessAudit.objects.create(
                            actor_id=request.user.pk,
                            object_id=contact.pk,
                            action='contact.assurance_qualification_updated',
                            metadata={
                                'before': before,
                                'after': data['qualification'],
                                'revision': contact.revision,
                            },
                        )
            response = Response(
                {
                    'fields': FIELDS,
                    'qualification': visible_qualification(contact.assurance_qualification),
                    'contact_revision': contact.revision,
                    'source': 'contact',
                }
            )
        else:
            raise PermissionDenied('Espace Assurance requis.')
        response['Cache-Control'] = 'no-store'
        return response
