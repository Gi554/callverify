"""Submit prospect SMS once per confirmed occurrence and notification kind."""

import secrets
from datetime import timedelta, timezone as utc
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

import phonenumbers
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.crypto import salted_hmac

from packages.newt import sms
from .isolation_mail import fetch
from .models import SmsAttempt
from .newt_sms import configured


def destination(raw):
    if not isinstance(raw, str):
        return None
    try:
        number = phonenumbers.parse(raw, 'CA')
    except phonenumbers.NumberParseException:
        return None
    if number.country_code == 1 and phonenumbers.is_valid_number(number):
        return str(number.national_number)
    return None


def notifications(visit, now):
    starts = parse_datetime(visit['starts_at'])
    created = parse_datetime(visit['created_at'])
    if starts <= now:
        return
    if created >= now - timedelta(days=7):
        yield 'confirmation'
    if created <= starts - timedelta(hours=24) and starts <= now + timedelta(hours=24):
        yield 'reminder'


def load(since, after=0, visit=0):
    return fetch(
        f'/api/internal/isolation/sms-visits/?since={since}&after={after}&visit={visit}',
        'sms_visits',
        since=since,
        after=after,
        visit=visit,
    )['visits']


def submit(visit, kind, since):
    phone = destination(visit['phone'])
    if phone is None:
        return 0
    starts = parse_datetime(visit['starts_at'])
    identifier = uuid5(
        NAMESPACE_URL, f'orvia/isolation/sms/{visit["id"]}/{starts.isoformat()}/{kind}'
    )
    if SmsAttempt.objects.filter(pk=identifier).exists():
        return 0
    # Recheck the current appointment and snapshot before claiming a send.
    if load(since, visit=visit['id']) != [visit]:
        return 0
    stamp = starts.astimezone(ZoneInfo('America/Toronto')).strftime('%d/%m/%Y à %H:%M')
    label = 'Confirmation' if kind == 'confirmation' else 'Rappel'
    message = f'{label} de votre visite Isolation le {stamp} (heure du Québec).'
    caller_id = settings.NEWT_SMS_CALLER_ID
    row, created = SmsAttempt.objects.get_or_create(
        pk=identifier,
        defaults={
            'kind': kind,
            'correlation': secrets.token_hex(5),
            'destination': phone,
            'caller_id': caller_id,
            'fingerprint': salted_hmac(
                'newt-sms-v1', phone + ':' + message, algorithm='sha256'
            ).hexdigest(),
        },
    )
    if not created:
        return 0
    row.state = sms.send(
        settings.NEWT_USERNAME,
        settings.NEWT_PASSWORD,
        phone,
        caller_id,
        message,
        row.correlation,
    )
    row.save(update_fields=['state'])
    return 1


def sync():
    if not configured() or not settings.NEWT_SMS_AUTOMATIC_FROM:
        return 0
    since = parse_datetime(settings.NEWT_SMS_AUTOMATIC_FROM)
    if since is None or timezone.is_naive(since):
        raise ValueError('A dated SMS activation is required')
    # Serialize UTC offsets safely in a URL without a raw plus sign.
    since = since.astimezone(utc.utc).isoformat().replace('+00:00', 'Z')

    count = 0
    after = 0
    while True:
        rows = load(since, after)
        for visit in rows:
            for kind in notifications(visit, timezone.now()):
                count += submit(visit, kind, since)
        if len(rows) < 100:
            return count
        after = rows[-1]['id']
