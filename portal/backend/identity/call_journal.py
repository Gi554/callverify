"""Reconcile CRM call commands with the NEWT 541 journal to record the provider's duration.

Only our own attempts are updated; the provider's global lines are never stored. A line matches
when it comes from the attempt's extension, reaches the same number (compared through a keyed
digest) and starts shortly after the command. Ambiguous cases are reported, never guessed.
"""

import hashlib
import hmac
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from packages.access.phone_history import number
from packages.newt.cdr import (
    duration_seconds,
    fetch_recordings,
    normalize_extension,
    PROVIDER_TIMEZONE,
)
from packages.newt.directory import DirectoryUnavailable
from .management_api import require_admin
from .models import PhoneCallAttempt, PhoneDirectoryGate, AccessAudit

# Compatibility seam for existing worker tests and integrations. The journal
# reader behind this name is now F=541, not the legacy 511 report.
fetch_records = fetch_recordings

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
                'extension': normalize_extension(row['from']),
                'digest': target,
                'at': instant,
                'duration': duration_seconds(raw),
                'uid': row.get('uid', ''),
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


def funnel(attempts, records, parsed):
    """Counts only: where commands stop matching journal lines. No number or time is kept."""
    extensions = {line['extension'] for line in parsed}
    digests = {line['digest'] for line in parsed}
    pairs = {}
    for line in parsed:
        pairs.setdefault((line['extension'], line['digest']), []).append(line['at'])
    same_extension = same_number = same_both = in_window = 0
    offsets = []
    for attempt in attempts:
        same_extension += attempt.extension in extensions
        same_number += attempt.destination_digest in digests
        instants = pairs.get((attempt.extension, attempt.destination_digest))
        if not instants:
            continue
        same_both += 1
        if any(attempt.created_at - BEFORE <= at <= attempt.created_at + AFTER for at in instants):
            in_window += 1
        else:
            # Signed gap to the closest line: a constant value reveals a clock or zone shift.
            offsets.append(
                min(((at - attempt.created_at).total_seconds() for at in instants), key=abs)
            )
    offsets.sort()
    return {
        'lines': len(records),
        'lines_dated_with_number': len(parsed),
        'lines_with_extension': sum(1 for line in parsed if line['extension']),
        'attempts_same_extension': same_extension,
        'attempts_same_number': same_number,
        'attempts_same_extension_and_number': same_both,
        'attempts_in_time_window': in_window,
        'median_gap_seconds_outside_window': (
            round(offsets[len(offsets) // 2]) if offsets else None
        ),
    }


def run(workspace, actor=None, now=None):
    try:
        return reconcile_recent(workspace, actor, now)
    except DirectoryUnavailable as error:
        # Written after the rollback so that an unreadable journal leaves a trace.
        AccessAudit.objects.create(
            user=actor,
            workspace=workspace,
            action='phone.journal_unreadable',
            metadata=getattr(error, 'diagnostic', {}),
        )
        raise


def reconcile_recent(workspace, actor=None, now=None):
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
            .filter(workspace=workspace, created_at__gte=since)
            .filter(Q(state__in=STATES) | Q(state='dispatching', created_at__lte=now - SETTLE))
            .exclude(journal_status='matched')
            .exclude(destination_digest='')
            .order_by('created_at')
        )
        summary = {'checked': len(attempts), 'matched': 0, 'ambiguous': 0, 'not_found': 0}
        if attempts:
            records = fetch_records(settings.NEWT_USERNAME, settings.NEWT_PASSWORD, start, today)
            results = reconcile(attempts, records, now)
            summary['diagnostic'] = funnel(attempts, records, lines(records))
            for attempt in attempts:
                status, line = results[attempt.pk]
                attempt.journal_status = status
                attempt.journal_checked_at = now
                if line:
                    attempt.journal_started_at = line['at']
                    attempt.journal_duration = line['duration']
                    attempt.journal_uid = line['uid']
                attempt.save(
                    update_fields=[
                        'journal_status',
                        'journal_checked_at',
                        'journal_started_at',
                        'journal_duration',
                        'journal_uid',
                    ]
                )
                if status in ('matched', 'ambiguous', 'not_found'):
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
    except DirectoryUnavailable as error:
        diagnostic = getattr(error, 'diagnostic', None)
        raise Unavailable(
            Unavailable.default_detail
            + (' Diagnostic : ' + json.dumps(diagnostic, ensure_ascii=False) if diagnostic else '')
        ) from None
    response = Response(summary)
    response['Cache-Control'] = 'no-store'
    return response
