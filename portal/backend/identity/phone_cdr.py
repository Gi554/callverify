"""Schema discovery only: call records are neither returned nor persisted."""

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from packages.newt.cdr import fetch_schema, confirmed, PROVIDER_TIMEZONE
from packages.newt.directory import DirectoryUnavailable
from .calendars import StrictInput, validated
from .management_api import require_admin
from .models import PhoneDirectoryGate, AccessAudit
from .phone_directory import DirectoryThrottle


class Window(StrictInput):
    starts_on = serializers.DateField(input_formats=['%Y-%m-%d'])
    ends_on = serializers.DateField(input_formats=['%Y-%m-%d'])

    def validate(self, data):
        super().validate(data)
        if (
            not 0 <= (data['ends_on'] - data['starts_on']).days <= 6
            or data['ends_on'] > timezone.localdate()
        ):
            raise ValidationError('Période passée ou courante de sept dates maximum requise')
        return data


class Unavailable(APIException):
    status_code = 503
    default_detail = 'Diagnostic des journaux NEWT indisponible, non configuré ou format non reconnu. Aucun résultat métier déduit.'


@api_view(['POST'])
@throttle_classes([DirectoryThrottle])
def schema(request):
    for space in ('assurance', 'isolation'):
        require_admin(request.user, space)
    if request.query_params:
        raise ValidationError('Aucun paramètre d’URL attendu')
    data = validated(Window, request.data)
    if (
        not settings.NEWT_CDR_SCHEMA_ENABLED
        or not settings.NEWT_USERNAME
        or not settings.NEWT_PASSWORD
    ):
        raise Unavailable()
    try:
        with transaction.atomic():
            PhoneDirectoryGate.objects.get_or_create(pk=1)
            PhoneDirectoryGate.objects.filter(pk=1).update(revision=F('revision'))
            for space in ('assurance', 'isolation'):
                require_admin(request.user, space)
            result = fetch_schema(
                settings.NEWT_USERNAME, settings.NEWT_PASSWORD, data['starts_on'], data['ends_on']
            )
            AccessAudit.objects.create(
                user=request.user,
                action='phone.cdr_schema_read',
                metadata={
                    'starts_on': str(data['starts_on']),
                    'ends_on': str(data['ends_on']),
                    'row_count': result['row_count'],
                    'schema_fingerprint': result['schema_fingerprint'],
                },
            )
    except DirectoryUnavailable:
        raise Unavailable() from None
    response = Response(
        {
            **result,
            'starts_on': data['starts_on'],
            'ends_on': data['ends_on'],
            'source': 'NEWT 511',
            'checked_at': timezone.now(),
            'mapping_confirmed': confirmed(result['columns']),
            'timezone': PROVIDER_TIMEZONE,
            'duration_unit_confirmed': False,
        }
    )
    response['Cache-Control'] = 'no-store'
    return response
