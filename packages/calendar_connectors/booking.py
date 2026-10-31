"""Fail closed bridge: business bookings cannot skip a configured external check."""

import json
from urllib.parse import urlsplit
import requests
from django.conf import settings
from rest_framework.exceptions import APIException
from packages.access.calendar_checks import issue


class Busy(APIException):
    status_code = 409
    default_detail = 'Créneau occupé dans l’agenda externe.'


class Unavailable(APIException):
    status_code = 503
    default_detail = 'Disponibilité externe impossible à vérifier ; réservation non confirmée.'


def check(
    user,
    advisor,
    start,
    end,
    source_id=None,
    workspace='assurance',
    include_busy=False,
    publication=False,
):
    base = settings.PORTAL_INTERNAL_URL.rstrip('/')
    parsed = urlsplit(base)
    if (
        parsed.scheme not in ('http', 'https')
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path
    ):
        raise Unavailable()
    proof = issue(user.pk, user.role, advisor, start, end, source_id, workspace)
    try:
        with requests.post(
            base
            + f'/api/portal/internal/{workspace}/calendar-'
            + ('periods/' if include_busy else 'ready/' if publication else 'check/'),
            json={'proof': proof},
            timeout=(5, 90),
            allow_redirects=False,
            stream=True,
            headers={'X-Forwarded-Proto': 'https'},
        ) as response:
            if response.status_code != 200:
                raise Unavailable()
            limit = 100000 if include_busy else 2048
            body = response.raw.read(limit + 1, decode_content=True)
            if len(body) > limit:
                raise Unavailable()
            result = json.loads(body)
    except (requests.RequestException, ValueError, UnicodeError):
        raise Unavailable() from None
    if (
        not isinstance(result, dict)
        or set(result)
        != ({'result', 'checked_at', 'busy'} if include_busy else {'result', 'checked_at'})
        or result['result'] not in ('free', 'busy', 'internal_only')
        or not isinstance(result['checked_at'], str)
    ):
        raise Unavailable()
    if include_busy:
        from django.utils.dateparse import parse_datetime
        from django.utils import timezone

        rows = result['busy']
        if not isinstance(rows, list) or len(rows) > 1000 or result['result'] == 'internal_only':
            raise Unavailable()
        for row in rows:
            if not isinstance(row, dict) or set(row) != {'start', 'end'}:
                raise Unavailable()
            try:
                first, last = [
                    parse_datetime(row[key]) if isinstance(row[key], str) else None
                    for key in ('start', 'end')
                ]
            except (ValueError, TypeError):
                raise Unavailable() from None
            if (
                first is None
                or last is None
                or timezone.is_naive(first)
                or timezone.is_naive(last)
                or not start <= first < last <= end
            ):
                raise Unavailable()
        return result
    if result['result'] == 'busy':
        raise Busy()
    return result
