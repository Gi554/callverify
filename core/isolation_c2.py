"""Isolation-only qualification. Drafts are internal; booked copies are immutable."""

import re
import unicodedata
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from .models import Prospect, AuditEvent, ImportRow


class C2Input(serializers.Serializer):
    full_name = serializers.CharField(max_length=250, allow_blank=True, default='')
    phone = serializers.CharField(max_length=40, allow_blank=True, default='')
    address = serializers.CharField(max_length=500, allow_blank=True, default='')
    city = serializers.CharField(max_length=150, allow_blank=True, default='')
    postal_code = serializers.CharField(max_length=10, allow_blank=True, default='')
    attic_accessible = serializers.BooleanField(allow_null=True, default=None)
    monthly_electricity = serializers.DecimalField(
        max_digits=9, decimal_places=2, min_value=0, allow_null=True, default=None
    )
    construction_year = serializers.IntegerField(min_value=1600, allow_null=True, default=None)
    age = serializers.IntegerField(min_value=0, max_value=120, allow_null=True, default=None)

    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise ValidationError('Champs C2 non autorisés.')
        return super().to_internal_value(data)

    def validate(self, data):
        if data['construction_year'] and data['construction_year'] > timezone.now().year:
            raise ValidationError({'construction_year': 'Année de construction future interdite.'})
        if data['postal_code']:
            postal = re.sub(r'\s', '', data['postal_code']).upper()
            if not re.fullmatch(
                r'[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTVWXYZ]\d[ABCEGHJ-NPRSTVWXYZ]\d', postal
            ):
                raise ValidationError({'postal_code': 'Code postal canadien attendu.'})
            data['postal_code'] = postal[:3] + ' ' + postal[3:]
        if data['phone'] and (
            not re.fullmatch(r'[+\d\s().-]+', data['phone'])
            or not 7 <= len(re.sub(r'\D', '', data['phone'])) <= 15
        ):
            raise ValidationError({'phone': 'Numéro de téléphone attendu.'})
        # Store decimals as strings to preserve their precision in JSON.
        if data['monthly_electricity'] is not None:
            data['monthly_electricity'] = str(data['monthly_electricity'])
        return data


def complete(value):
    serializer = C2Input(data=value)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    missing = [
        key
        for key, value in data.items()
        if key not in ('monthly_electricity', 'age') and (value is None or value == '')
    ]
    if missing:
        raise ValidationError(
            {'c2': {key: 'À renseigner avant la réservation.' for key in missing}}
        )
    return data


def captured(prospect):
    return {
        'version': 1,
        'captured_at': timezone.now().isoformat(),
        'campaign_id': prospect.campaign_id,
        'setter_id': prospect.assigned_setter_id,
        'fields': complete(prospect.c2),
    }


def defaults(prospect):
    """Only recognized columns from the original nonduplicate import, never guess a value."""
    result = {'full_name': prospect.name, 'phone': prospect.raw_phone}
    imported = (
        ImportRow.objects.filter(prospect=prospect, duplicate=False, error='')
        .order_by('pk')
        .first()
    )
    if not imported or not isinstance(imported.source, dict):
        return result
    aliases = {
        'address': ('address', 'adresse', 'adressecomplete', 'fulladdress'),
        'city': ('city', 'ville', 'municipalite'),
        'postal_code': ('postalcode', 'codepostal', 'postcode'),
    }

    def normalize(key):
        value = unicodedata.normalize('NFKD', str(key)).encode('ascii', 'ignore').decode().lower()
        return re.sub('[^a-z0-9]', '', value)

    source = {normalize(key): value for key, value in imported.source.items()}
    for field, keys in aliases.items():
        found = [
            str(source[key]).strip()
            for key in keys
            if key in source and source[key] is not None and str(source[key]).strip()
        ]
        # Conflicting columns are left empty for human review.
        if not found or len(set(found)) != 1:
            continue
        serializer = C2Input(data={field: found[0]})
        if serializer.is_valid():
            result[field] = serializer.validated_data[field]
    return result


class DraftInput(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0)
    c2 = C2Input()

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés.')
        return data


class C2Mixin:
    @action(detail=True, methods=['get', 'post'])
    def c2(self, request, pk=None):
        from .isolation_work import Conflict

        row = self.get_object()
        if request.method == 'POST':
            serializer = DraftInput(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            with transaction.atomic():
                rows = Prospect.objects.filter(pk=row.pk, assignment_revision=data['revision'])
                if request.user.role == 'setter':
                    rows = rows.filter(assigned_setter_id=request.user.pk)
                if not rows.update(c2=data['c2'], assignment_revision=F('assignment_revision') + 1):
                    raise Conflict(
                        'Fiche modifiée ou réattribuée : rechargez avant d’enregistrer le C2.'
                    )
                AuditEvent.objects.create(
                    action='isolation.prospect.c2_saved',
                    object_id=str(row.pk),
                    metadata={
                        'actor_portal_id': request.user.pk,
                        'before': row.c2,
                        'after': data['c2'],
                        'revision': data['revision'] + 1,
                    },
                )
            row.refresh_from_db()
        response = Response(
            {
                'c2': row.c2,
                'revision': row.assignment_revision,
                'defaults': defaults(row),
            }
        )
        response['Cache-Control'] = 'no-store'
        return response
