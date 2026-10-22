from datetime import timedelta
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import serializers
from rest_framework.decorators import api_view, action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from .models import ContactFieldSchema, Contact, BusinessAudit
from .leases import Conflict, held, LEASE_SECONDS


class FieldDefinition(serializers.Serializer):
    key = serializers.RegexField(r'^[a-z][a-z0-9_]{0,39}$')
    label = serializers.CharField(max_length=100)
    type = serializers.ChoiceField(choices=['text', 'boolean', 'date', 'choice'])
    required = serializers.BooleanField(default=False)
    active = serializers.BooleanField(default=True)
    advisor_visible = serializers.BooleanField(default=False)
    choices = serializers.ListField(
        child=serializers.CharField(max_length=100), max_length=50, default=list
    )

    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise ValidationError('Propriété de champ inconnue')
        return super().to_internal_value(data)

    def validate(self, data):
        if data['type'] == 'choice':
            if not data['choices'] or len(data['choices']) != len(set(data['choices'])):
                raise ValidationError('Liste de choix distincts requise')
        elif data['choices']:
            raise ValidationError('Choix réservés au type liste')
        return data


class SchemaInput(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0)
    fields = FieldDefinition(many=True)
    reason = serializers.CharField(max_length=1000)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés')
        if len(data['fields']) > 30 or len({item['key'] for item in data['fields']}) != len(
            data['fields']
        ):
            raise ValidationError('Maximum 30 clés distinctes')
        return data


def internal(user):
    if user.role not in ('administrator', 'setter'):
        raise PermissionDenied('Champs internes Assurance uniquement')


def schema():
    return ContactFieldSchema.objects.filter(pk=1).first() or ContactFieldSchema(pk=1)


def output(row):
    return {'fields': row.fields, 'revision': row.revision}


@api_view(['GET', 'POST'])
def definitions(request):
    internal(request.user)
    if request.method == 'GET':
        return Response(output(schema()))
    if request.user.role != 'administrator':
        raise PermissionDenied('Configuration réservée à l’administration')
    serializer = SchemaInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    with transaction.atomic():
        ContactFieldSchema.objects.get_or_create(pk=1)
        row = ContactFieldSchema.objects.get(pk=1)
        if row.revision != data['revision']:
            raise Conflict('Configuration modifiée : actualisez')
        new = {item['key']: item for item in data['fields']}
        for old in row.fields:
            item = new.get(old['key'])
            if item is None or item['type'] != old['type'] or item['choices'] != old['choices']:
                raise ValidationError(
                    'Conservez les clés, types et choix existants. Désactivez un champ pour l’archiver.'
                )
        before = output(row)
        if not ContactFieldSchema.objects.filter(pk=1, revision=data['revision']).update(
            fields=data['fields'], revision=F('revision') + 1
        ):
            raise Conflict('Configuration modifiée : actualisez')
        row.refresh_from_db()
        BusinessAudit.objects.create(
            actor_id=request.user.pk,
            object_id=1,
            action='schema.contact_fields_changed',
            metadata={'before': before, 'after': output(row), 'reason': data['reason']},
        )
    return Response(output(row))


class ValuesInput(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0)
    schema_revision = serializers.IntegerField(min_value=0)
    token = serializers.UUIDField()
    values = serializers.DictField()

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés')
        return data


def validate_values(values, fields):
    active = {item['key']: item for item in fields if item['active']}
    if set(values) - set(active):
        raise ValidationError('Clé inconnue ou champ archivé')
    for key, item in active.items():
        value = values.get(key)
        if value is None or value == '':
            if item['required']:
                raise ValidationError({key: 'Champ obligatoire'})
            continue
        kind = item['type']
        if kind == 'text' and (not isinstance(value, str) or len(value) > 2000):
            raise ValidationError({key: 'Texte de 2 000 caractères maximum requis'})
        if kind == 'boolean' and type(value) is not bool:
            raise ValidationError({key: 'Booléen requis'})
        if kind == 'choice' and (not isinstance(value, str) or value not in item['choices']):
            raise ValidationError({key: 'Choix invalide'})
        if kind == 'date':
            try:
                valid = (
                    isinstance(value, str) and len(value) == 10 and parse_date(value) is not None
                )
            except ValueError:
                valid = False
            if not valid:
                raise ValidationError({key: 'Date AAAA-MM-JJ requise'})
        if kind == 'text' and item['required'] and not value.strip():
            raise ValidationError({key: 'Champ obligatoire'})


class CustomValuesMixin:
    @action(detail=True, methods=['get'])
    def shared_fields(self, request, pk=None):
        if request.user.role != 'advisor':
            raise PermissionDenied('Consultation réservée au conseiller du dossier')
        contact = self.get_object()
        fields = [
            {
                'key': item['key'],
                'label': item['label'],
                'type': item['type'],
                'value': contact.custom_values.get(item['key']),
            }
            for item in schema().fields
            if item.get('active') is True and item.get('advisor_visible') is True
        ]
        response = Response({'fields': fields})
        response['Cache-Control'] = 'no-store'
        return response

    @action(detail=True, methods=['get', 'post'])
    def custom_fields(self, request, pk=None):
        internal(request.user)
        contact = self.get_object()
        if request.method == 'GET':
            return Response(
                {
                    'schema': output(schema()),
                    'values': contact.custom_values,
                    'revision': contact.revision,
                }
            )
        serializer = ValuesInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            now = timezone.now()
            if not held(contact.pk, request.user, data['token'], now).update(
                lease_expires_at=now + timedelta(seconds=LEASE_SECONDS)
            ):
                raise Conflict('Prise en charge requise')
            ContactFieldSchema.objects.get_or_create(pk=1)
            # Serialize with schema changes before validating the field set.
            ContactFieldSchema.objects.filter(pk=1).update(revision=F('revision'))
            rules = ContactFieldSchema.objects.get(pk=1)
            if rules.revision != data['schema_revision']:
                raise Conflict('Configuration modifiée : rechargez les champs')
            contact = Contact.objects.get(pk=contact.pk)
            if contact.revision != data['revision']:
                raise Conflict('Fiche modifiée : rechargez avant de saisir')
            validate_values(data['values'], rules.fields)
            archived = {item['key'] for item in rules.fields if not item['active']}
            new = {key: value for key, value in contact.custom_values.items() if key in archived}
            new.update(data['values'])
            before = contact.custom_values
            if new != before:
                contact.custom_values = new
                contact.revision += 1
                contact.save(update_fields=['custom_values', 'revision', 'updated_at'])
                BusinessAudit.objects.create(
                    actor_id=request.user.pk,
                    object_id=contact.pk,
                    action='contact.custom_fields_changed',
                    metadata={
                        'before': before,
                        'after': new,
                        'schema_revision': rules.revision,
                        'revision': contact.revision,
                    },
                )
        return Response(
            {'schema': output(rules), 'values': contact.custom_values, 'revision': contact.revision}
        )
