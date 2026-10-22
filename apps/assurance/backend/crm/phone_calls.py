"""Authorize one explicit call from a currently leased contact; no provider access."""

import re
from django.db import transaction
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from packages.access.phone_calls import issue, verify
from django.core import signing
from django.utils import timezone
from .leases import held
from .agreements import lock_contact
from .models import BusinessAudit
from packages.access.history_actions import HistoryMixin


class Intent(serializers.Serializer):
    token = serializers.UUIDField(write_only=True)
    contact_revision = serializers.IntegerField(min_value=0)
    request_id = serializers.UUIDField()

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Seuls jeton, version et identifiant de demande sont acceptés.')
        return data


def dial_number(raw):
    # Dial formatting only; never changes the source or determines line validity.
    if not isinstance(raw, str) or not re.fullmatch(r'\+?[0-9 ().-]+', raw):
        raise ValidationError('Numéro nord-américain sans extension requis pour composer.')
    digits = re.sub(r'[ ().-]', '', raw).removeprefix('+')
    if len(digits) == 10:
        digits = '1' + digits
    if not re.fullmatch(r'1[2-9][0-9]{2}[2-9][0-9]{6}', digits):
        raise ValidationError('Numéro nord-américain composable requis ; corrigez la fiche.')
    return digits


class PhoneCallMixin(HistoryMixin):
    history_workspace = 'assurance'

    @action(detail=True, methods=['post'], url_path='call-intent')
    def call_intent(self, request, pk=None):
        if request.user.role != 'setter':
            raise PermissionDenied('Seul le setter connecté peut autoriser son propre appel.')
        if request.query_params:
            raise ValidationError('Aucun paramètre de requête autorisé.')
        serializer = Intent(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            contact = lock_contact(self.get_object(), request.user, data)
            proof = issue(
                request.user.pk,
                contact.pk,
                contact.revision,
                data['request_id'],
                dial_number(contact.phone),
                data['token'],
            )
            BusinessAudit.objects.create(
                actor_id=request.user.pk,
                object_id=contact.pk,
                action='contact.call_intent',
                metadata={'request_id': str(data['request_id']), 'revision': contact.revision},
            )
        response = Response(
            {'proof': proof, 'expires_in': 60, 'request_id': str(data['request_id'])}
        )
        response['Cache-Control'] = 'no-store'
        return response

    @action(detail=True, methods=['post'], url_path='call-intent-check')
    def call_intent_check(self, request, pk=None):
        if request.user.role != 'setter':
            raise PermissionDenied('Setter requis.')
        if request.query_params or set(request.data) != {'proof'}:
            raise ValidationError('Preuve seule requise.')
        try:
            claims = verify(request.data['proof'], request.user.pk)
        except (signing.BadSignature, TypeError, ValueError, AttributeError):
            raise ValidationError('Preuve invalide ou expirée.') from None
        contact = self.get_object()
        eligible = (
            claims['contact'] == contact.pk
            and claims['revision'] == contact.revision
            and held(contact.pk, request.user, claims['lease'], timezone.now()).exists()
            and dial_number(contact.phone) == claims['destination']
        )
        response = Response({'eligible': bool(eligible)})
        response['Cache-Control'] = 'no-store'
        return response
