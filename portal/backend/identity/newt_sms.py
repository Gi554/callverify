"""Administrator-only manual SMS with a durable single submission per request."""

import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.crypto import salted_hmac
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response

from packages.newt import sms
from .management_api import require_admin
from .models import SmsAttempt


class SmsInput(serializers.Serializer):
    request_id = serializers.UUIDField()
    destination = serializers.RegexField(r'^[2-9][0-9]{2}[2-9][0-9]{6}$', max_length=10)
    message = serializers.CharField(max_length=1600, trim_whitespace=False)

    def validate_message(self, value):
        if not value.strip() or '\x00' in value:
            raise serializers.ValidationError('Saisissez un message SMS.')
        return value


def output(row):
    state = row.state
    if state == 'dispatching' and row.created_at < timezone.now() - timedelta(minutes=2):
        state = 'unknown'
    return {
        'request_id': str(row.request_id),
        'destination': row.destination,
        'caller_id': row.caller_id,
        'state': state,
        'kind': row.kind,
        'created_at': row.created_at,
    }


def configured():
    caller_id = settings.NEWT_SMS_CALLER_ID
    return bool(
        settings.NEWT_SMS_ENABLED
        and settings.NEWT_USERNAME
        and settings.NEWT_PASSWORD
        and re.fullmatch(r'[2-9][0-9]{2}[2-9][0-9]{6}', caller_id)
    )


@api_view(['GET', 'POST'])
def messages(request):
    require_admin(request.user, 'isolation')
    caller_id = settings.NEWT_SMS_CALLER_ID
    enabled = configured()
    if request.method == 'GET':
        response = Response(
            {
                'enabled': enabled,
                'caller_id': caller_id if enabled else '',
                'results': [output(row) for row in SmsAttempt.objects.order_by('-created_at')[:25]],
            }
        )
        response['Cache-Control'] = 'no-store'
        return response

    form = SmsInput(data=request.data)
    form.is_valid(raise_exception=True)
    data = form.validated_data
    fingerprint = salted_hmac(
        'newt-sms-v1', data['destination'] + ':' + data['message'], algorithm='sha256'
    ).hexdigest()
    existing = SmsAttempt.objects.filter(pk=data['request_id']).first()
    if existing is None and not enabled:
        return Response({'detail': 'Envoi SMS NEWT non configuré.'}, status=503)
    row, created = (
        (existing, False)
        if existing
        else SmsAttempt.objects.get_or_create(
            pk=data['request_id'],
            defaults={
                'actor': request.user,
                'correlation': secrets.token_hex(5),
                'destination': data['destination'],
                'caller_id': caller_id,
                'fingerprint': fingerprint,
            },
        )
    )
    if row.actor_id != request.user.pk or row.fingerprint != fingerprint:
        return Response({'detail': 'Identifiant de demande déjà utilisé.'}, status=409)
    if created:
        row.state = sms.send(
            settings.NEWT_USERNAME,
            settings.NEWT_PASSWORD,
            row.destination,
            row.caller_id,
            data['message'],
            row.correlation,
        )
        row.save(update_fields=['state'])
    return Response(output(row), status=201 if created else 200)
