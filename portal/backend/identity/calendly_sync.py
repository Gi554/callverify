"""Durable webhook processing and replay-safe delivery to Assurance."""

import json
from datetime import timedelta
from uuid import UUID, uuid4

from django.conf import settings
from django.db import transaction
from django.db.models import Q, F
from django.utils import timezone
from rest_framework.exceptions import APIException

from packages.calendar_connectors import calendly as provider
from packages.calendar_connectors.providers import ProviderError, instant
from packages.calendar_connectors.calendly_bridge import rpc
from .calendars import seal, unseal
from .calendly_booking import credential, email_digest
from .models import CalendlyReservation, CalendlyInvitee, CalendlyWebhookReceipt, Membership


def enabled(row):
    return (
        row.connection.connected
        and Membership.objects.filter(
            user_id=row.connection.user_id,
            user__is_active=True,
            workspace='assurance',
            role='advisor',
            active=True,
        ).exists()
    )


def locate(hook, clean):
    refs = [clean['invitee'], clean.get('old_invitee'), clean.get('new_invitee')]
    matches = set(
        CalendlyInvitee.objects.filter(
            uri__in=[value for value in refs if value],
            reservation__connection=hook.connection,
            reservation__owner_uri=hook.owner_uri,
        ).values_list('reservation_id', flat=True)
    )
    identifier = clean.get('request_id')
    if identifier:
        candidate = CalendlyReservation.objects.filter(
            pk=UUID(identifier), connection=hook.connection, owner_uri=hook.owner_uri
        ).first()
        if candidate:
            matches.add(candidate.pk)
    if len(matches) > 1:
        raise ProviderError(code='ambiguous_reference')
    if matches:
        return CalendlyReservation.objects.select_related('connection').get(pk=matches.pop())
    # Known initial responses can predate the invitee reference table.
    return None


def deliver(row):
    if (
        row.state != 'confirmed'
        or row.revision <= row.delivered_revision
        or not row.payload
        or not enabled(row)
    ):
        return
    state = unseal(row.payload)
    public = {
        key: state.get(key, '')
        for key in ('invitee', 'starts_at', 'ends_at', 'status', 'cancel_url', 'reschedule_url')
    }
    result = rpc(
        settings.ASSURANCE_INTERNAL_URL.rstrip('/'),
        'assurance',
        'deliver',
        {
            'request_id': str(row.pk),
            'owner': row.connection.user_id,
            'revision': row.revision,
            'appointment': public,
        },
    )
    if (
        result.get('result') not in ('applied', 'duplicate', 'review')
        or result.get('revision') != row.revision
    ):
        raise ProviderError(code='delivery_unavailable')
    if result['result'] == 'review':
        raise ProviderError(code='crm_review')
    CalendlyReservation.objects.filter(pk=row.pk, revision=row.revision).update(
        delivered_revision=row.revision
    )


def reconcile(row, incoming=None):
    now, claim = timezone.now(), uuid4()
    if (
        not CalendlyReservation.objects.filter(pk=row.pk)
        .filter(Q(lease_until__isnull=True) | Q(lease_until__lt=now))
        .update(lease_until=now + timedelta(minutes=5), claim=claim)
    ):
        raise ProviderError(code='processing')
    try:
        row.refresh_from_db()
        if not enabled(row):
            return
        _, _, tokens = credential(row.connection.user_id)
        if tokens['owner'] != row.owner_uri:
            raise ProviderError(code='reconnect_original_account')
        previous = unseal(row.payload) if row.payload else {}
        start_uri = previous.get('invitee') or (incoming or {}).get('invitee')
        if not start_uri:
            # A lost POST response is recovered by a signed webhook with the opaque request ID.
            raise ProviderError(code='awaiting_webhook')
        canonical, visited = None, []
        for _ in range(10):
            uri = provider.invitee_uri(start_uri)
            if uri in visited:
                raise ProviderError(code='invalid_chain')
            visited.append(uri)
            canonical = provider.appointment(tokens['access'], uri, row.owner_uri, row.event_type)
            if not previous.get('invitee'):
                # A tracking value alone cannot bind an unrelated meeting to a CRM prospect.
                email = canonical.get('email')
                if (
                    not isinstance(email, str)
                    or not row.email_digest
                    or email_digest(row.pk, email) != row.email_digest
                    or instant(canonical['starts_at']) != row.expected_start
                    or instant(canonical['ends_at']) != row.expected_end
                ):
                    raise ProviderError(code='unmatched_booking')
                previous = {'invitee': uri}
            if canonical.get('new_invitee'):
                start_uri = canonical['new_invitee']
                continue
            if canonical['status'] == 'cancelled' and canonical.get('rescheduled'):
                raise ProviderError(code='provider_propagation')
            break
        else:
            raise ProviderError(code='invalid_chain')
        if (
            incoming
            and incoming['invitee'] not in visited
            and not CalendlyInvitee.objects.filter(
                reservation=row, uri=incoming['invitee']
            ).exists()
        ):
            raise ProviderError(code='provider_propagation')
        canonical.pop('email', None)
        canonical.pop('request_id', None)
        with transaction.atomic():
            locked = (
                CalendlyReservation.objects.select_for_update()
                .select_related('connection')
                .get(pk=row.pk)
            )
            if locked.claim != claim or not enabled(locked):
                return
            for uri in visited:
                reference, _ = CalendlyInvitee.objects.get_or_create(
                    uri=uri, defaults={'reservation': locked}
                )
                if reference.reservation_id != locked.pk:
                    raise ProviderError(code='ambiguous_reference')
            old = unseal(locked.payload) if locked.payload else {}
            if (
                json.dumps(old, sort_keys=True) != json.dumps(canonical, sort_keys=True)
                or locked.state != 'confirmed'
            ):
                locked.payload = seal(canonical)
                locked.state = 'confirmed'
                locked.revision += 1
            locked.checked_at = timezone.now()
            locked.save()
            row = locked
        deliver(row)
    finally:
        CalendlyReservation.objects.filter(pk=row.pk, claim=claim).update(
            lease_until=None, claim=None
        )


def process_receipt(pk):
    now = timezone.now()
    owned_lease = now + timedelta(minutes=5)
    if (
        not CalendlyWebhookReceipt.objects.filter(pk=pk, next_attempt_at__lte=now)
        .filter(Q(state__in=['pending', 'retry']) | Q(state='processing', lease_until__lte=now))
        .update(state='processing', lease_until=owned_lease)
    ):
        return 'skipped'
    item = CalendlyWebhookReceipt.objects.select_related('webhook__connection').get(pk=pk)
    try:
        if not item.webhook.connection.connected or item.webhook.state not in (
            'active',
            'registering',
            'uncertain',
        ):
            item.state = 'ignored'
        else:
            clean = unseal(item.payload)
            row = locate(item.webhook, clean)
            if row:
                reconcile(row, clean)
                item.state = 'done'
            else:
                item.state = 'ignored'
        item.payload = ''
        item.error_code = ''
    except (ProviderError, APIException, ValueError, TypeError, KeyError):
        item.attempts += 1
        item.state = 'retry' if item.attempts < 20 else 'review'
        item.error_code = 'synchronization_unavailable'
        item.next_attempt_at = timezone.now() + timedelta(
            seconds=min(3600, 5 * 2 ** min(item.attempts, 10))
        )
    changed = CalendlyWebhookReceipt.objects.filter(
        pk=item.pk, state='processing', lease_until=owned_lease
    ).update(
        lease_until=None,
        state=item.state,
        payload=item.payload,
        attempts=item.attempts,
        error_code=item.error_code,
        next_attempt_at=item.next_attempt_at,
    )
    return item.state if changed else 'skipped'


def sweep(limit=20):
    now = timezone.now()
    counts = {}
    ids = list(
        CalendlyWebhookReceipt.objects.filter(next_attempt_at__lte=now)
        .filter(Q(state__in=['pending', 'retry']) | Q(state='processing', lease_until__lte=now))
        .order_by('pk')
        .values_list('pk', flat=True)[:limit]
    )
    for pk in ids:
        state = process_receipt(pk)
        counts[state] = counts.get(state, 0) + 1
    # Reconcile known invitees periodically as a backstop for missed/out-of-order notifications.
    rows = (
        CalendlyReservation.objects.select_related('connection')
        .filter(state__in=['confirmed', 'uncertain'], connection__connected=True)
        .filter(
            Q(state='uncertain')
            | Q(delivered_revision__lt=F('revision'))
            | Q(expected_end__isnull=True)
            | Q(expected_end__gt=now - timedelta(days=30))
        )
        .filter(Q(checked_at__isnull=True) | Q(checked_at__lt=now - timedelta(minutes=5)))
        .order_by(F('checked_at').asc(nulls_first=True), 'pk')[:limit]
    )
    for row in rows:
        try:
            reconcile(row)
            counts['checked'] = counts.get('checked', 0) + 1
        except (ProviderError, APIException, ValueError, TypeError, KeyError):
            CalendlyReservation.objects.filter(pk=row.pk).update(checked_at=timezone.now())
            counts['unavailable'] = counts.get('unavailable', 0) + 1
    return counts
