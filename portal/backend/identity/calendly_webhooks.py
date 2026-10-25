"""Signed, bounded webhook intake. Provider reads and CRM writes run in the worker."""

import hashlib
import hmac
import json
import time
import re
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.views.decorators.cache import never_cache
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from packages.calendar_connectors import calendly as provider
from packages.calendar_connectors.providers import ProviderError
from . import calendly
from .calendars import require_owner, seal, validated, RevisionInput
from .calendly_booking import credential
from .models import CalendlyWebhook, CalendlyWebhookReceipt
from .recovery import public_url


def configured():
    return (
        isinstance(settings.CALENDLY_WEBHOOK_SIGNING_KEY, str)
        and len(settings.CALENDLY_WEBHOOK_SIGNING_KEY) >= 16
    )


def url(hook):
    return public_url() + '/api/portal/calendly/webhook/' + str(hook.pk) + '/'


def status(user):
    hook = CalendlyWebhook.objects.filter(connection__user=user).order_by('-checked_at').first()
    return {
        'configured': configured(),
        'state': hook.state if hook else 'inactive',
        'checked_at': hook.checked_at if hook else None,
        'pending': CalendlyWebhookReceipt.objects.filter(
            webhook__connection__user=user, state__in=['pending', 'retry', 'processing']
        ).count(),
        'needs_review': CalendlyWebhookReceipt.objects.filter(
            webhook__connection__user=user, state='review'
        ).count(),
    }


@never_cache
@api_view(['GET', 'POST'])
def configuration(request):
    require_owner(request.user, 'assurance')
    if request.method == 'GET':
        return Response(status(request.user))
    data = validated(RevisionInput, request.data)
    if not configured():
        raise calendly.Unavailable()
    row, _, tokens = credential(request.user.pk)
    if row.revision != data['revision']:
        raise ValidationError('Connexion actualisée. Rechargez avant de réessayer.')
    try:
        organization = provider.resource_uri(tokens.get('organization'), 'organizations')
        hook, _ = CalendlyWebhook.objects.get_or_create(
            connection=row, owner_uri=tokens['owner'], defaults={'organization': organization}
        )
        existing = provider.find_webhook(tokens['access'], organization, tokens['owner'], url(hook))
        if not existing:
            # A timeout may have created a subscription. Never blindly POST it a second time.
            if not CalendlyWebhook.objects.filter(pk=hook.pk, create_attempted=False).update(
                create_attempted=True, state='registering'
            ):
                raise calendly.Unavailable()
            existing = provider.create_webhook(
                tokens['access'], organization, tokens['owner'], url(hook)
            )
        with transaction.atomic():
            locked = calendly.lock(request.user)
            require_owner(request.user, 'assurance')
            changed = not locked.connected or locked.revision != row.revision
            if changed:
                CalendlyWebhook.objects.filter(pk=hook.pk).update(state='inactive')
            else:
                hook.subscription = existing
                hook.state = 'active'
                hook.checked_at = timezone.now()
                hook.save()
                CalendlyWebhookReceipt.objects.filter(webhook=hook, state='review').update(
                    state='retry',
                    attempts=0,
                    next_attempt_at=timezone.now(),
                    lease_until=None,
                    error_code='',
                )
                calendly.audit(request.user, 'webhook_activated')
        if changed:
            raise ValidationError('Connexion modifiée pendant l’activation.')
        return Response(status(request.user))
    except ProviderError as error:
        changes = {'state': 'uncertain'}
        if error.code == 'rejected':
            changes.update(state='rejected', create_attempted=False)
        CalendlyWebhook.objects.filter(connection=row, owner_uri=tokens['owner']).update(**changes)
        raise calendly.Unavailable() from None


def signature(raw, header):
    if not configured() or not isinstance(header, str) or len(header) > 2048:
        raise PermissionDenied('Signature Calendly requise.')
    fields = {}
    for part in header.split(','):
        key, sep, value = part.strip().partition('=')
        if not sep or key not in ('t', 'v1'):
            raise PermissionDenied('Signature Calendly invalide.')
        fields.setdefault(key, []).append(value)
    timestamps, hashes = fields.get('t', []), fields.get('v1', [])
    if (
        len(timestamps) != 1
        or not re.fullmatch(r'[0-9]+', timestamps[0])
        or len(timestamps[0]) > 12
        or not 1 <= len(hashes) <= 4
    ):
        raise PermissionDenied('Signature Calendly invalide.')
    if abs(time.time() - int(timestamps[0])) > 180:
        raise PermissionDenied('Signature Calendly expirée.')
    expected = hmac.new(
        settings.CALENDLY_WEBHOOK_SIGNING_KEY.encode(),
        timestamps[0].encode() + b'.' + raw,
        hashlib.sha256,
    ).hexdigest()
    if not any(
        re.fullmatch(r'[0-9a-f]{64}', value) and hmac.compare_digest(expected, value)
        for value in hashes
    ):
        raise PermissionDenied('Signature Calendly invalide.')


@never_cache
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def receive(request, hook_id):
    if not configured():
        raise calendly.Unavailable()
    raw = request.stream.read(262145) if request.stream else b''
    if len(raw) > 262144:
        return Response(status=413)
    signature(raw, request.headers.get('Calendly-Webhook-Signature'))
    hook = CalendlyWebhook.objects.filter(
        pk=hook_id, connection__connected=True, state__in=['registering', 'active', 'uncertain']
    ).first()
    if not hook:
        return Response(status=204)
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get('event') not in (
            'invitee.created',
            'invitee.canceled',
        ):
            return Response(status=204)
        body = data.get('payload')
        if not isinstance(body, dict):
            raise ValueError()
        clean = {'event': data['event'], 'invitee': provider.invitee_uri(body.get('uri'))}
        for key in ('old_invitee', 'new_invitee'):
            clean[key] = provider.invitee_uri(body[key]) if body.get(key) else None
        tracking = body.get('tracking') or {}
        identifier = tracking.get('utm_content') if isinstance(tracking, dict) else None
        try:
            clean['request_id'] = str(UUID(identifier)) if isinstance(identifier, str) else None
        except ValueError:
            clean['request_id'] = None
    except (ValueError, TypeError, ProviderError):
        raise ValidationError('Notification Calendly invalide.') from None
    CalendlyWebhookReceipt.objects.get_or_create(
        webhook=hook,
        digest=hashlib.sha256(raw).hexdigest(),
        defaults={
            'payload': seal(clean),
            'next_attempt_at': timezone.now(),
        },
    )
    return Response(status=202)
