"""Independent per-adviser Calendly OAuth connection; no central paid seats."""

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.views.decorators.cache import never_cache
from rest_framework import serializers
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response

from packages.calendar_connectors import calendly as provider
from packages.calendar_connectors.providers import ProviderError
from .calendars import (
    CallbackInput,
    RevisionInput,
    CalendarThrottle,
    StrictInput,
    cipher,
    require_owner,
    seal,
    session_hash,
    unseal,
    validated,
)
from .models import AccessAudit, CalendlyAuthorization, CalendlyConnection
from .recovery import public_url


class Unavailable(APIException):
    status_code = 503
    default_detail = 'Calendly indisponible. Actualisez ou reconnectez votre compte si nécessaire.'


class SelectionInput(RevisionInput):
    event_type = serializers.CharField(max_length=300, allow_blank=True)


def config():
    if not settings.CALENDLY_CLIENT_ID or not settings.CALENDLY_CLIENT_SECRET:
        raise Unavailable()
    try:
        redirect = public_url() + '/crm/oauth/calendly'
        cipher()
    except (ValueError, APIException):
        raise Unavailable() from None
    return {
        'client_id': settings.CALENDLY_CLIENT_ID,
        'client_secret': settings.CALENDLY_CLIENT_SECRET,
        'redirect': redirect,
    }


def reply(data=None, status=200):
    response = Response(data, status=status)
    response['Cache-Control'] = 'no-store'
    return response


def audit(user, action):
    AccessAudit.objects.create(user=user, workspace='assurance', action='calendly.' + action)


def lock(user):
    row, _ = CalendlyConnection.objects.get_or_create(user=user)
    # Write lock works on SQLite too; serialize refreshes of single-use refresh tokens.
    CalendlyConnection.objects.filter(pk=row.pk).update(revision=F('revision'))
    row.refresh_from_db()
    return row


def save(row, payload):
    row.payload = seal(payload)
    row.revision += 1
    row.save(update_fields=['payload', 'revision', 'expires_at', 'connected', 'checked_at'])


def clear(row):
    row.payload = ''
    row.connected = False
    row.expires_at = None
    row.checked_at = None
    row.revision += 1
    row.save()


def view(row, ready):
    payload = unseal(row.payload) if row and row.connected else {}
    return {
        'configured': ready,
        'connected': bool(row and row.connected),
        'revision': row.revision if row else 0,
        'profile': payload.get('profile'),
        'event_types': payload.get('event_types', []),
        'selected_event_type': payload.get('selected', ''),
        'checked_at': row.checked_at if row else None,
        'booking_in_crm': False,
    }


@never_cache
@api_view(['GET'])
@throttle_classes([CalendarThrottle])
def connection(request):
    require_owner(request.user, 'assurance')
    try:
        config()
        ready = True
    except Unavailable:
        ready = False
    return reply(view(CalendlyConnection.objects.filter(user=request.user).first(), ready))


@never_cache
@api_view(['POST'])
@throttle_classes([CalendarThrottle])
def start(request):
    require_owner(request.user, 'assurance')
    validated(StrictInput, request.data)
    options = config()
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    with transaction.atomic():
        row = lock(request.user)
        row.revision += 1
        row.save(update_fields=['revision'])
        CalendlyAuthorization.objects.filter(
            user=request.user, expires_at__lte=timezone.now()
        ).delete()
        CalendlyAuthorization.objects.filter(user=request.user, used=False).update(
            used=True, verifier=''
        )
        CalendlyAuthorization.objects.create(
            user=request.user,
            state_hash=hashlib.sha256(state.encode()).hexdigest(),
            session_hash=session_hash(request),
            verifier=seal(verifier),
            revision=row.revision,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        audit(request.user, 'authorization_started')
    return reply({'authorization_url': provider.authorization(options, state, verifier)})


@never_cache
@api_view(['POST'])
@throttle_classes([CalendarThrottle])
def callback(request):
    require_owner(request.user, 'assurance')
    data = validated(CallbackInput, request.data)
    options = config()
    attempt = CalendlyAuthorization.objects.filter(
        user=request.user,
        state_hash=hashlib.sha256(data['state'].encode()).hexdigest(),
        session_hash=session_hash(request),
        used=False,
        expires_at__gt=timezone.now(),
    ).first()
    if not attempt or not CalendlyAuthorization.objects.filter(
        pk=attempt.pk, used=False, expires_at__gt=timezone.now()
    ).update(used=True, verifier=''):
        raise ValidationError('Autorisation expirée, déjà utilisée ou liée à une autre session')
    if 'error' in data:
        raise ValidationError('Autorisation Calendly refusée. Vous pouvez recommencer.')
    try:
        tokens, seconds = provider.tokens(
            options, code=data['code'], verifier=unseal(attempt.verifier)
        )
        profile = provider.profile(tokens['access'], tokens['owner'])
        types = provider.event_types(tokens['access'], tokens['owner'])
    except ProviderError:
        raise Unavailable() from None
    with transaction.atomic():
        row = lock(request.user)
        require_owner(request.user, 'assurance')
        if row.revision != attempt.revision:
            raise ValidationError('Connexion modifiée. Recommencez depuis Calendly.')
        row.connected = True
        row.expires_at = timezone.now() + timedelta(seconds=seconds)
        row.checked_at = timezone.now()
        save(row, {'tokens': tokens, 'profile': profile, 'event_types': types, 'selected': ''})
        audit(request.user, 'connected')
        return reply(view(row, True))


@never_cache
@api_view(['POST'])
@throttle_classes([CalendarThrottle])
def refresh(request):
    require_owner(request.user, 'assurance')
    data = validated(RevisionInput, request.data)
    options = config()
    failed = False
    permission_error = None
    with transaction.atomic():
        row = lock(request.user)
        if not row.connected or row.revision != data['revision']:
            raise ValidationError('Connexion modifiée. Rechargez la page.')
        payload = unseal(row.payload)
        tokens = payload['tokens']
        if not row.expires_at or row.expires_at <= timezone.now() + timedelta(seconds=60):
            try:
                rotated, seconds = provider.tokens(options, refresh=tokens['refresh'])
                if rotated['owner'] != tokens['owner']:
                    raise ProviderError(True)
                payload['tokens'] = tokens = rotated
                row.expires_at = timezone.now() + timedelta(seconds=seconds)
                save(row, payload)
            except ProviderError:
                # Ambiguous timeout may have spent the old token. Never retry it.
                clear(row)
                audit(request.user, 'reauthorization_required')
                failed = True
        if not failed:
            try:
                profile = provider.profile(tokens['access'], tokens['owner'])
                types = provider.event_types(tokens['access'], tokens['owner'])
                require_owner(request.user, 'assurance')
                payload.update(profile=profile, event_types=types)
                if payload.get('selected') not in {entry['uri'] for entry in types}:
                    payload['selected'] = ''
                row.checked_at = timezone.now()
                save(row, payload)
                audit(request.user, 'refreshed')
            except APIException as error:
                # Do not roll back an already rotated refresh token after a role change.
                clear(row)
                permission_error = error
                failed = True
            except ProviderError as error:
                if error.reauthorize:
                    clear(row)
                    audit(request.user, 'reauthorization_required')
                failed = True
        result = view(row, True)
    if failed:
        if permission_error:
            raise permission_error
        raise Unavailable()
    return reply(result)


@never_cache
@api_view(['POST'])
@throttle_classes([CalendarThrottle])
def selection(request):
    require_owner(request.user, 'assurance')
    data = validated(SelectionInput, request.data)
    with transaction.atomic():
        row = lock(request.user)
        if not row.connected or row.revision != data['revision']:
            raise ValidationError('Connexion modifiée. Rechargez la page.')
        payload = unseal(row.payload)
        if data['event_type'] and data['event_type'] not in {
            item['uri'] for item in payload['event_types']
        }:
            raise ValidationError('Choisissez une page proposée par votre compte Calendly.')
        payload['selected'] = data['event_type']
        save(row, payload)
        audit(request.user, 'selection_changed')
        return reply(
            view(row, bool(settings.CALENDLY_CLIENT_ID and settings.CALENDLY_CLIENT_SECRET))
        )


@never_cache
@api_view(['POST'])
@throttle_classes([CalendarThrottle])
def disconnect(request):
    # An authenticated former adviser can still delete their own credentials.
    data = validated(RevisionInput, request.data)
    with transaction.atomic():
        row = lock(request.user)
        if row.revision != data['revision']:
            raise ValidationError('Connexion modifiée. Rechargez la page.')
        clear(row)
        CalendlyAuthorization.objects.filter(user=request.user, used=False).update(
            used=True, verifier=''
        )
        audit(request.user, 'disconnected')
    return reply(status=204)
