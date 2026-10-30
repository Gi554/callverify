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
from .models import Campaign, PhoneNumber, Prospect, Suppression, AuditEvent
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


class QuickCall(serializers.Serializer):
    phone = serializers.CharField(max_length=40)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Seul le numéro est accepté.')
        return data


def dial_digits(raw):
    if not re.fullmatch(r'\+?[0-9 ().-]+', raw):
        raise ValidationError('Numéro nord-américain sans extension requis pour composer.')
    digits = re.sub(r'[ ().-]', '', raw).removeprefix('+')
    if len(digits) == 10:
        digits = '1' + digits
    if not re.fullmatch(r'1[2-9][0-9]{2}[2-9][0-9]{6}', digits):
        raise ValidationError('Numéro nord-américain composable requis.')
    return digits


class IsolationPhoneCallMixin(HistoryMixin):
    history_workspace = 'isolation'

    @action(detail=False, methods=['post'], url_path='quick-call')
    def quick_call(self, request):
        """Dial pad: the prospect holding this number, or a new one, so the call stays on a file."""
        from .isolation_qualification import WORKSPACE, service_owner
        from .isolation_work import visible

        if request.user.role not in ('setter', 'administrator'):
            raise PermissionDenied('Seul un setter ou administrateur peut composer un numéro.')
        serializer = QuickCall(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw = serializer.validated_data['phone'].strip()
        e164 = '+' + dial_digits(raw)
        if Suppression.objects.filter(e164=e164).exists():
            raise ValidationError('Numéro exclu : appel interdit.')
        with transaction.atomic():
            known = list(Prospect.objects.filter(phone__e164=e164).order_by('pk'))
            mine = [row for row in known if visible(request.user).filter(pk=row.pk).exists()]
            if mine:
                row = mine[0]
                if row.compliance != 'allowed':
                    raise ValidationError(
                        'Cette fiche attend l’autorisation d’appel d’un administrateur.'
                    )
                return Response({'id': row.pk, 'created': False})
            if known:
                raise PermissionDenied(
                    'Ce numéro correspond à une fiche confiée à un autre setter.'
                )
            phone, _ = PhoneNumber.objects.get_or_create(e164=e164, defaults={'validity': 'valid'})
            campaign = Campaign.objects.filter(
                portal_workspace=WORKSPACE, name='Appels directs'
            ).first() or Campaign.objects.create(
                owner=service_owner(),
                portal_workspace=WORKSPACE,
                portal_owner_id=request.user.pk,
                name='Appels directs',
                purpose='Numéros composés à la main depuis le composeur',
                source='Composeur',
            )
            row = Prospect.objects.create(
                campaign=campaign,
                phone=phone,
                raw_phone=raw,
                validity='valid',
                compliance='allowed',
                compliance_reason='Appel libre : numéro composé par l’utilisateur',
                assigned_setter_id=request.user.pk,
            )
            AuditEvent.objects.create(
                action='isolation.prospect.quick_call_created',
                object_id=str(row.pk),
                metadata={'actor_portal_id': request.user.pk},
            )
        return Response({'id': row.pk, 'created': True}, status=201)

    @action(detail=True, methods=['post'], url_path='call-intent')
    def call_intent(self, request, pk=None):
        from .isolation_work import Conflict

        if request.user.role not in ('setter', 'administrator'):
            raise PermissionDenied('Setter ou administrateur requis pour demander son appel.')
        if request.query_params:
            raise ValidationError('Paramètres interdits.')
        serializer = Input(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        prospect = self.get_object()
        with transaction.atomic():
            scoped = Prospect.objects.filter(pk=prospect.pk, assignment_revision=data['revision'])
            if request.user.role == 'setter':
                scoped = scoped.filter(assigned_setter_id=request.user.pk)
            if not scoped.update(assignment_revision=F('assignment_revision')):
                raise Conflict('Prospect modifié ou réattribué.')
            row = Prospect.objects.select_related('phone').get(pk=prospect.pk)
            proof = issue(
                request.user.pk,
                row.pk,
                row.assignment_revision,
                data['request_id'],
                destination(row),
                workspace='isolation',
                label=row.name,
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
        if request.user.role not in ('setter', 'administrator'):
            raise PermissionDenied('Setter ou administrateur requis.')
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
