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


def check(user, advisor, start, end, source_id=None, workspace='assurance'):
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
            base + f'/api/portal/internal/{workspace}/calendar-check/',
            json={'proof': proof},
            timeout=(5, 90),
            allow_redirects=False,
            stream=True,
            headers={'X-Forwarded-Proto': 'https'},
        ) as response:
            if response.status_code != 200:
                raise Unavailable()
            body = response.raw.read(2049, decode_content=True)
            if len(body) > 2048:
                raise Unavailable()
            result = json.loads(body)
    except (requests.RequestException, ValueError, UnicodeError):
        raise Unavailable() from None
    if (
        not isinstance(result, dict)
        or set(result) != {'result', 'checked_at'}
        or result['result'] not in ('free', 'busy', 'internal_only')
        or not isinstance(result['checked_at'], str)
    ):
        raise Unavailable()
    if result['result'] == 'busy':
        raise Busy()
    return result
