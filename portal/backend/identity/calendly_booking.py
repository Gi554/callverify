"""Service-only availability and single-dispatch Calendly reservations."""

import hashlib
import json
from datetime import timedelta
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from django.views.decorators.cache import never_cache
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from packages.calendar_connectors import calendly as provider
from packages.calendar_connectors.providers import ProviderError, instant
from packages.calendar_connectors.calendly_bridge import verify
from . import calendly
from .calendars import CalendarThrottle, seal, unseal
from .models import Membership, CalendlyConnection, CalendlyReservation


def actor(data):
    if (
        type(data.get('actor')) is not int
        or data.get('role') not in ('setter', 'administrator')
        or not Membership.objects.filter(
            user_id=data['actor'],
            user__is_active=True,
            workspace='assurance',
            role=data['role'],
            active=True,
        ).exists()
    ):
        raise PermissionDenied('Setter ou administrateur Assurance actif requis.')
    if (
        type(data.get('owner')) is not int
        or not Membership.objects.filter(
            user_id=data['owner'],
            user__is_active=True,
            workspace='assurance',
            role='advisor',
            active=True,
        ).exists()
    ):
        raise PermissionDenied('Conseiller Assurance actif requis.')


def credential(owner):
    failed = False
    with transaction.atomic():
        row = (
            CalendlyConnection.objects.select_for_update()
            .filter(user_id=owner, connected=True)
            .first()
        )
        if not row:
            raise calendly.Unavailable()
        # SQLite tests also acquire a write lock through the existing helper.
        row = calendly.lock(row.user)
        payload = unseal(row.payload)
        tokens = payload['tokens']
        if not set(provider.BOOKING_SCOPES) <= set(tokens.get('scopes', [])):
            raise ValidationError(
                'Le conseiller doit reconnecter Calendly pour autoriser la réservation.'
            )
        if not row.expires_at or row.expires_at <= timezone.now() + timedelta(seconds=60):
            try:
                fresh, seconds = provider.tokens(calendly.config(), refresh=tokens['refresh'])
                if fresh['owner'] != tokens['owner'] or not set(provider.BOOKING_SCOPES) <= set(
                    fresh.get('scopes', [])
                ):
                    raise ProviderError(True)
                payload['tokens'] = tokens = fresh
                row.expires_at = timezone.now() + timedelta(seconds=seconds)
                calendly.save(row, payload)
            except ProviderError:
                calendly.clear(row)
                failed = True
    if failed:
        raise calendly.Unavailable()
    return row, payload, tokens


def result(row):
    return {
        'state': row.state,
        'request_id': str(row.pk),
        'appointment': unseal(row.payload) if row.payload else None,
    }


def execute(action, data):
    actor(data)
    if action == 'reserve':
        try:
            existing = CalendlyReservation.objects.filter(pk=UUID(data['request_id'])).first()
            canonical = {
                key: data[key]
                for key in (
                    'actor',
                    'owner',
                    'request_id',
                    'event_type',
                    'starts_at',
                    'ends_at',
                    'name',
                    'email',
                )
            }
            fingerprint = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
        except (ValueError, TypeError, KeyError):
            raise ValidationError('Demande de réservation invalide.') from None
        if existing:
            if (
                existing.fingerprint != fingerprint
                or existing.actor_id != data['actor']
                or existing.connection.user_id != data['owner']
            ):
                raise ValidationError('Identifiant de réservation déjà utilisé.')
            return result(existing)
    if action == 'status':
        try:
            row = CalendlyReservation.objects.get(
                pk=UUID(data['request_id']),
                actor_id=data['actor'],
                connection__user_id=data['owner'],
            )
        except (ValueError, KeyError, CalendlyReservation.DoesNotExist):
            raise ValidationError('Demande Calendly inconnue.') from None
        return result(row)
    row, payload, tokens = credential(data['owner'])
    selected = next(
        (item for item in payload.get('event_types', []) if item['uri'] == payload.get('selected')),
        None,
    )
    if not selected:
        raise ValidationError('Le conseiller doit choisir une page Calendly personnelle.')
    if action == 'configuration':
        return {
            'event_type': selected['uri'],
            'name': selected['name'],
            'duration': selected['duration'],
            'timezone': 'America/Toronto',
        }
    start, end = instant(data.get('starts_at')), instant(data.get('ends_at'))
    if not timezone.now() < start < end <= start + timedelta(days=7):
        raise ValidationError('Période future limitée à sept jours.')
    if action == 'slots':
        return {
            **selected,
            'slots': provider.times(tokens['access'], selected['uri'], start, end),
            'timezone': 'America/Toronto',
        }
    if (
        action != 'reserve'
        or data.get('event_type') != selected['uri']
        or end - start != timedelta(minutes=selected['duration'])
    ):
        raise ValidationError('Page ou durée Calendly modifiée. Rechargez les créneaux.')
    try:
        identifier = UUID(data['request_id'])
        name, email = data['name'], data['email']
        if (
            not isinstance(name, str)
            or not 1 <= len(name.strip()) <= 250
            or not isinstance(email, str)
            or len(email) > 254
        ):
            raise ValueError()
        validate_email(email)
    except (ValueError, KeyError, TypeError, DjangoValidationError):
        raise ValidationError('Nom et courriel valides requis pour Calendly.') from None
    canonical = {
        key: data[key]
        for key in (
            'actor',
            'owner',
            'request_id',
            'event_type',
            'starts_at',
            'ends_at',
            'name',
            'email',
        )
    }
    fingerprint = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
    # Persist dispatch intent BEFORE the provider write. A timeout must never trigger a replay.
    reservation, created = CalendlyReservation.objects.get_or_create(
        request_id=identifier,
        defaults={
            'connection': row,
            'actor_id': data['actor'],
            'fingerprint': fingerprint,
            'owner_uri': tokens['owner'],
            'event_type': selected['uri'],
        },
    )
    if not created:
        if reservation.fingerprint != fingerprint or reservation.connection_id != row.pk:
            raise ValidationError('Identifiant de réservation déjà utilisé.')
        return result(reservation)
    dispatched = False
    try:
        available = provider.times(
            tokens['access'], selected['uri'], start, start + timedelta(minutes=1)
        )
        if start.isoformat() not in available:
            reservation.state = 'rejected'
        else:
            actor(data)
            dispatched = True
            uri = provider.create_invitee(
                tokens['access'], selected['uri'], start, name, email, identifier
            )
            reservation.payload = seal({'invitee': uri})
            reservation.state = 'uncertain'
            reservation.save()
            canonical = provider.appointment(
                tokens['access'], uri, tokens['owner'], selected['uri']
            )
            if instant(canonical['starts_at']) != start or instant(canonical['ends_at']) != end:
                raise ProviderError(code='uncertain')
            reservation.payload = seal(canonical)
            reservation.state = 'confirmed'
    except ProviderError as error:
        reservation.state = (
            'rejected' if not dispatched or error.code == 'rejected' else 'uncertain'
        )
    reservation.save()
    return result(reservation)


@never_cache
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([CalendarThrottle])
def internal(request):
    if (
        not isinstance(request.data, dict)
        or set(request.data) != {'proof'}
        or not isinstance(request.data['proof'], str)
        or len(request.data['proof']) > 20000
    ):
        raise ValidationError('Preuve serveur seule requise.')
    action, data = verify(request.data['proof'], {'configuration', 'slots', 'reserve', 'status'})
    try:
        return Response(execute(action, data))
    except ProviderError:
        raise calendly.Unavailable() from None
