"""Administrators hand out lots of unprocessed prospects to setters, and take them back."""

from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from .assignments import admin
from .models import AdvisorAssignment, BusinessAudit, Contact, ContactImport
from .prospect_queue import apply_queue

MAX_LOT = 1000


class LotInput(serializers.Serializer):
    request_id = serializers.UUIDField()
    setter_id = serializers.IntegerField(min_value=1)
    count = serializers.IntegerField(min_value=1, max_value=MAX_LOT)
    import_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés')
        return data


class ReleaseInput(serializers.Serializer):
    request_id = serializers.UUIDField()
    setter_id = serializers.IntegerField(min_value=1)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés')
        return data


def setters():
    """Setters known to Assurance through an active advisor association."""
    names = {}
    for row in AdvisorAssignment.objects.filter(active=True).order_by('setter_name', 'pk'):
        names.setdefault(row.setter_id, row.setter_name)
    return names


def unassigned():
    return apply_queue(Contact.objects.filter(assigned_setter_id__isnull=True), 'active')


def done(request_id):
    return BusinessAudit.objects.filter(
        action__in=('lot.assigned', 'lot.released'), metadata__request_id=str(request_id)
    ).first()


def summary():
    owned = {
        row['assigned_setter_id']: row['n']
        for row in apply_queue(Contact.objects.filter(assigned_setter_id__isnull=False), 'active')
        .values('assigned_setter_id')
        .annotate(n=Count('pk'))
    }
    free = unassigned()
    per_import = {
        row['import_batch_id']: row['n']
        for row in free.filter(import_batch__isnull=False)
        .values('import_batch_id')
        .annotate(n=Count('pk'))
    }
    imports = [
        {'id': row.pk, 'filename': row.filename, 'available': per_import[row.pk]}
        for row in ContactImport.objects.filter(pk__in=per_import).order_by('-pk')[:50]
    ]
    return {
        'available': free.count(),
        'setters': [
            {'id': pk, 'name': name, 'assigned': owned.get(pk, 0)} for pk, name in setters().items()
        ],
        'imports': imports,
    }


@api_view(['GET', 'POST'])
def lots(request):
    admin(request.user)
    if request.method == 'GET':
        response = Response(summary())
        response['Cache-Control'] = 'no-store'
        return response
    serializer = LotInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    previous = done(data['request_id'])
    if previous:
        return Response({'assigned': previous.metadata.get('count', 0), 'replayed': True})
    name = setters().get(data['setter_id'])
    if name is None:
        raise ValidationError(
            'Ce setter n’a aucun conseiller associé : créez d’abord l’association.'
        )
    with transaction.atomic():
        qs = unassigned()
        if data.get('import_id'):
            qs = qs.filter(import_batch_id=data['import_id'])
        ids = list(qs.order_by('pk').values_list('pk', flat=True)[: data['count']])
        count = Contact.objects.filter(pk__in=ids, assigned_setter_id__isnull=True).update(
            assigned_setter_id=data['setter_id'],
            assigned_setter_name=name,
            assigned_at=timezone.now(),
        )
        BusinessAudit.objects.create(
            actor_id=request.user.pk,
            object_id=data['setter_id'],
            action='lot.assigned',
            metadata={
                'request_id': str(data['request_id']),
                'count': count,
                'import_id': data.get('import_id'),
            },
        )
    return Response({'assigned': count}, status=201)


@api_view(['POST'])
def release(request):
    admin(request.user)
    serializer = ReleaseInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    previous = done(data['request_id'])
    if previous:
        return Response({'released': previous.metadata.get('count', 0), 'replayed': True})
    with transaction.atomic():
        ids = list(
            apply_queue(Contact.objects.filter(assigned_setter_id=data['setter_id']), 'active')
            .filter(lease_owner_id__isnull=True)
            .values_list('pk', flat=True)
        )
        count = Contact.objects.filter(pk__in=ids).update(
            assigned_setter_id=None, assigned_setter_name='', assigned_at=None
        )
        BusinessAudit.objects.create(
            actor_id=request.user.pk,
            object_id=data['setter_id'],
            action='lot.released',
            metadata={'request_id': str(data['request_id']), 'count': count},
        )
    return Response({'released': count})
