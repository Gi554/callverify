"""Reconcile CRM call commands with the NEWT 511 journal to record the provider's duration.

Only our own attempts are updated; the provider's global lines are never stored. A line matches
when it comes from the attempt's extension, reaches the same number (compared through a keyed
digest) and starts shortly after the command. Ambiguous cases are reported, never guessed.
"""

import hashlib
import hmac
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from packages.access.phone_history import number
from packages.newt.cdr import fetch_records, PROVIDER_TIMEZONE
from packages.newt.directory import DirectoryUnavailable
from .management_api import require_admin
from .models import PhoneCallAttempt, PhoneDirectoryGate, AccessAudit

# The extension rings first (up to 30 s), then the number is dialed: allow clock drift before.
BEFORE = timedelta(seconds=60)
AFTER = timedelta(minutes=3)
# Lines may reach the journal late: an attempt is only "not found" after this delay.
SETTLE = timedelta(minutes=15)
DAYS = 7
STATES = ('accepted', 'unknown')


class Unavailable(APIException):
    status_code = 503
    default_detail = (
        'Journal NEWT indisponible, non configuré ou format non reconnu. Aucune durée modifiée.'
    )


def digest(destination):
    return hmac.new(
        settings.SECRET_KEY.encode(), ('newt-destination:' + destination).encode(), hashlib.sha256
    ).hexdigest()


def lines(records):
    parsed = []
    for row in records:
        try:
            instant = datetime.fromisoformat(row['occurred_at']) if row['occurred_at'] else None
            target = digest(number(row['to']))
        except (ValueError, TypeError):
            continue
        if instant is None or timezone.is_naive(instant):
            continue
        raw = row['duration_raw'].strip()
        parsed.append(
            {
                'extension': row['from'],
                'digest': target,
                'at': instant,
                'duration': int(raw) if raw.isdigit() else None,
            }
        )
    return parsed


def reconcile(attempts, records, now):
    """Return {request_id: (status, line)} for each attempt."""
    parsed = lines(records)
    candidates = {
        attempt.pk: [
            index
            for index, line in enumerate(parsed)
            if line['extension'] == attempt.extension
            and line['digest'] == attempt.destination_digest
            and attempt.created_at - BEFORE <= line['at'] <= attempt.created_at + AFTER
        ]
        for attempt in attempts
    }
    claimed = {}
    for indexes in candidates.values():
        for index in indexes:
            claimed[index] = claimed.get(index, 0) + 1
    results = {}
    for attempt in attempts:
        indexes = candidates[attempt.pk]
        if len(indexes) == 1 and claimed[indexes[0]] == 1:
            results[attempt.pk] = ('matched', parsed[indexes[0]])
        elif indexes:
            results[attempt.pk] = ('ambiguous', None)
        elif now - attempt.created_at >= SETTLE:
            results[attempt.pk] = ('not_found', None)
        else:
            results[attempt.pk] = ('pending', None)
    return results


def run(workspace, actor=None, now=None):
    now = now or timezone.now()
    zone = ZoneInfo(PROVIDER_TIMEZONE)
    today = now.astimezone(zone).date()
    start = today - timedelta(days=DAYS - 1)
    since = datetime.combine(start, datetime.min.time(), tzinfo=zone)
    with transaction.atomic():
        # Same gate as the other provider reads: one journal request at a time.
        PhoneDirectoryGate.objects.get_or_create(pk=1)
        PhoneDirectoryGate.objects.filter(pk=1).update(revision=F('revision'))
        attempts = list(
            PhoneCallAttempt.objects.select_for_update()
            .filter(workspace=workspace, state__in=STATES, created_at__gte=since)
            .exclude(journal_status='matched')
            .exclude(destination_digest='')
            .order_by('created_at')
        )
        summary = {'checked': len(attempts), 'matched': 0, 'ambiguous': 0, 'not_found': 0}
        if attempts:
            records = fetch_records(settings.NEWT_USERNAME, settings.NEWT_PASSWORD, start, today)
            results = reconcile(attempts, records, now)
            for attempt in attempts:
                status, line = results[attempt.pk]
                attempt.journal_status = status
                attempt.journal_checked_at = now
                if line:
                    attempt.journal_started_at = line['at']
                    attempt.journal_duration = line['duration']
                attempt.save(
                    update_fields=[
                        'journal_status',
                        'journal_checked_at',
                        'journal_started_at',
                        'journal_duration',
                    ]
                )
                if status in summary:
                    summary[status] += 1
        AccessAudit.objects.create(
            user=actor,
            workspace=workspace,
            action='phone.journal_reconciled',
            metadata={**summary, 'starts_on': str(start), 'ends_on': str(today)},
        )
    return summary


def configured():
    return bool(
        settings.NEWT_CDR_HISTORY_ENABLED and settings.NEWT_USERNAME and settings.NEWT_PASSWORD
    )


@api_view(['POST'])
def reconcile_view(request, workspace):
    require_admin(request.user, workspace)
    if not configured():
        raise Unavailable()
    try:
        summary = run(workspace, request.user)
    except DirectoryUnavailable:
        raise Unavailable() from None
    response = Response(summary)
    response['Cache-Control'] = 'no-store'
    return response
