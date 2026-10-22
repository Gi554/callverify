"""Explicit single-call authorization for an assigned, administratively allowed prospect."""

import re
from django.core import signing
from django.db import transaction
from django.db.models import F
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from packages.access.phone_calls import issue, verify
from .models import Prospect, Suppression, AuditEvent
from packages.access.history_actions import HistoryMixin


class Input(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0)
    request_id = serializers.UUIDField()

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Seuls révision et identifiant de demande sont acceptés.')
        return data


def destination(row):
    if row.compliance != 'allowed':
        raise ValidationError('Autorisation administrative d’appel requise.')
    if row.validity == 'invalid' or not row.phone_id:
        raise ValidationError('Numéro technique utilisable requis.')
    value = row.phone.e164
    if not re.fullmatch(r'\+1[2-9][0-9]{2}[2-9][0-9]{6}', value):
        raise ValidationError('Numéro nord-américain normalisé requis.')
    if Suppression.objects.filter(e164=value).exists():
        raise ValidationError('Numéro exclu : appel interdit.')
    return value[1:]


class IsolationPhoneCallMixin(HistoryMixin):
    history_workspace = 'isolation'

    @action(detail=True, methods=['post'], url_path='call-intent')
    def call_intent(self, request, pk=None):
        from .isolation_work import Conflict

        if request.user.role != 'setter':
            raise PermissionDenied('Seul le setter connecté peut demander son appel.')
        if request.query_params:
            raise ValidationError('Paramètres interdits.')
        serializer = Input(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        prospect = self.get_object()
        with transaction.atomic():
            if not Prospect.objects.filter(
                pk=prospect.pk,
                assigned_setter_id=request.user.pk,
                assignment_revision=data['revision'],
            ).update(assignment_revision=F('assignment_revision')):
                raise Conflict('Prospect modifié ou réattribué.')
            row = Prospect.objects.select_related('phone').get(pk=prospect.pk)
            proof = issue(
                request.user.pk,
                row.pk,
                row.assignment_revision,
                data['request_id'],
                destination(row),
                workspace='isolation',
            )
            AuditEvent.objects.create(
                action='isolation.prospect.call_intent',
                object_id=str(row.pk),
                metadata={
                    'actor_portal_id': request.user.pk,
                    'setter_name': row.assigned_setter_name,
                    'request_id': str(data['request_id']),
                    'revision': row.assignment_revision,
                },
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
            claims = verify(request.data['proof'], request.user.pk, 'isolation')
        except (signing.BadSignature, ValueError, TypeError, AttributeError):
            raise ValidationError('Preuve invalide ou expirée.') from None
        row = self.get_object()
        try:
            eligible = (
                claims['contact'] == row.pk
                and claims['revision'] == row.assignment_revision
                and claims['destination'] == destination(row)
            )
        except ValidationError:
            eligible = False
        response = Response({'eligible': bool(eligible)})
        response['Cache-Control'] = 'no-store'
        return response
