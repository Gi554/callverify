"""Durable one-shot command ledger. No ambiguous request is automatically retried."""

import hashlib
import json
import requests
from urllib.parse import urlsplit
from datetime import timedelta
from uuid import UUID
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.db import transaction, IntegrityError
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError, APIException
from rest_framework.response import Response
from packages.access.phone_calls import verify
from packages.access.tickets import issue as access_ticket
from packages.newt.calls import place
from .models import Membership, PhoneExtension, PhoneCallAttempt, AccessAudit
from .call_journal import digest


class Conflict(APIException):
    status_code = 409
    default_detail = 'Demande déjà utilisée ou appel trop récent.'


class Unavailable(APIException):
    status_code = 503
    default_detail = 'Appels Phonetico non activés.'


def caller_access(user, workspace='assurance'):
    member = Membership.objects.filter(
        user=user, workspace=workspace, role__in=('setter', 'administrator'), active=True
    ).first()
    if not user.is_active or member is None:
        raise PermissionDenied('Setter ou administrateur actif requis dans cet espace.')
    return member


def output(row):
    return {
        'request_id': str(row.request_id),
        ('contact_id' if row.workspace == 'assurance' else 'prospect_id'): row.contact_id,
        'workspace': row.workspace,
        'state': row.state,
        'created_at': row.created_at,
        'updated_at': row.updated_at,
        'definition': 'Success Phonetico = le poste émetteur a répondu et la composition extérieure démarre. Cela ne prouve ni sonnerie distante ni décrochage du destinataire. Failure = rappel au poste échoué selon le fournisseur. Indéterminé/en cours : aucune relance automatique.',
    }


def reply(row):
    response = Response(output(row))
    response['Cache-Control'] = 'no-store'
    return response


def eligible(user, claims, proof, workspace='assurance'):
    base = (
        settings.ASSURANCE_INTERNAL_URL
        if workspace == 'assurance'
        else settings.ISOLATION_INTERNAL_URL
    ).rstrip('/')
    parsed = urlsplit(base)
    if (
        parsed.scheme not in ('http', 'https')
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        return False
    path = (
        f'/api/assurance/contacts/{claims["contact"]}/call-intent-check/'
        if workspace == 'assurance'
        else f'/api/work-queue/{claims["contact"]}/call-intent-check/'
    )
    try:
        with requests.post(
            base + path,
            json={'proof': proof},
            headers={
                'Authorization': 'Bearer '
                + access_ticket(user.pk, workspace, caller_access(user, workspace).role)
            },
            timeout=(5, 5),
            allow_redirects=False,
            stream=True,
        ) as response:
            if response.status_code != 200:
                return False
            body = response.raw.read(1025, decode_content=True)
            return len(body) <= 1024 and json.loads(body) == {'eligible': True}
    except (requests.RequestException, ValueError, UnicodeError):
        return False


class Input(serializers.Serializer):
    proof = serializers.CharField(max_length=8192, write_only=True)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Seule la preuve de la fiche est acceptée.')
        return data


@api_view(['POST'])
def calls(request, workspace='assurance'):
    caller_access(request.user, workspace)
    if request.query_params:
        raise ValidationError('Paramètres interdits.')
    serializer = Input(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        claims = verify(serializer.validated_data['proof'], request.user.pk, workspace)
    except (signing.BadSignature, ValueError, TypeError, AttributeError, UnicodeError):
        raise ValidationError('Autorisation de fiche absente, invalide ou expirée.') from None
    fingerprint = hashlib.sha256(json.dumps(claims, sort_keys=True).encode()).hexdigest()
    with transaction.atomic():
        # Serialize requests for one caller, including differing request UUIDs.
        if (
            not get_user_model()
            .objects.filter(pk=request.user.pk, is_active=True)
            .update(password=F('password'))
        ):
            raise PermissionDenied('Compte indisponible.')
        caller_access(request.user, workspace)
        row = PhoneCallAttempt.objects.filter(pk=claims['request_id']).first()
        if row:
            if (
                row.user_id != request.user.pk
                or row.workspace != workspace
                or row.fingerprint != fingerprint
            ):
                raise Conflict('Identifiant déjà utilisé pour un autre contenu.')
            return reply(row)
        if (
            not settings.NEWT_CALLS_ENABLED
            or (workspace == 'isolation' and not settings.NEWT_ISOLATION_CALLS_ENABLED)
            or not settings.NEWT_USERNAME
            or not settings.NEWT_PASSWORD
        ):
            raise Unavailable()
        link = PhoneExtension.objects.filter(user=request.user, extension__isnull=False).first()
        if not link:
            raise ValidationError('Aucun poste associé à votre compte.')
        if PhoneCallAttempt.objects.filter(
            user=request.user, created_at__gt=timezone.now() - timedelta(seconds=60)
        ).exists():
            raise Conflict('Attendez au moins 60 secondes entre deux commandes distinctes.')
        try:
            with transaction.atomic():
                row = PhoneCallAttempt.objects.create(
                    request_id=UUID(claims['request_id']),
                    user=request.user,
                    workspace=workspace,
                    contact_id=claims['contact'],
                    contact_label=claims['label'],
                    extension=link.extension,
                    fingerprint=fingerprint,
                    destination_digest=digest(claims['destination']),
                )
        except IntegrityError:
            raise Conflict('Identifiant déjà réservé ; aucune nouvelle commande envoyée.') from None
        AccessAudit.objects.create(
            user=request.user,
            workspace=workspace,
            action='phone.call_reserved',
            metadata={
                'request_id': str(row.pk),
                ('contact_id' if row.workspace == 'assurance' else 'prospect_id'): row.contact_id,
                'workspace': row.workspace,
            },
        )
        extension = link.extension
    # Ledger is committed before touching the PBX: a timeout/process crash cannot
    # turn a repeated HTTP submission into a second provider command.
    try:
        if not eligible(request.user, claims, serializer.validated_data['proof'], workspace):
            state = 'blocked'
        else:
            state = place(
                settings.NEWT_USERNAME, settings.NEWT_PASSWORD, extension, claims['destination']
            )
    except Exception:
        state = 'unknown'
    if state not in ('accepted', 'rejected', 'unknown', 'blocked'):
        state = 'unknown'
    with transaction.atomic():
        PhoneCallAttempt.objects.filter(pk=row.pk, state='dispatching').update(
            state=state, updated_at=timezone.now()
        )
        AccessAudit.objects.create(
            user=request.user,
            workspace=workspace,
            action='phone.call_result',
            metadata={'request_id': str(row.pk), 'state': state},
        )
    row.refresh_from_db()
    return reply(row)


@api_view(['GET'])
def options(request, workspace='assurance'):
    caller_access(request.user, workspace)
    enabled = bool(
        settings.NEWT_CALLS_ENABLED
        and (workspace != 'isolation' or settings.NEWT_ISOLATION_CALLS_ENABLED)
        and settings.NEWT_USERNAME
        and settings.NEWT_PASSWORD
    )
    linked = PhoneExtension.objects.filter(user=request.user, extension__isnull=False).exists()
    response = Response({'enabled': enabled, 'post_associated': linked})
    response['Cache-Control'] = 'no-store'
    return response


@api_view(['GET'])
def status(request, request_id, workspace='assurance'):
    caller_access(request.user, workspace)
    return reply(
        get_object_or_404(PhoneCallAttempt, pk=request_id, user=request.user, workspace=workspace)
    )
