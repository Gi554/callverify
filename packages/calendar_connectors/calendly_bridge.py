"""Signed server-only RPC between the Assurance and identity databases."""

import json
from urllib.parse import urlsplit

import requests
from django.core import signing
from rest_framework.exceptions import APIException, PermissionDenied
from packages.access.tickets import key_for


class Unavailable(APIException):
    status_code = 503
    default_detail = 'Calendly indisponible. La réservation ne peut pas être confirmée.'


def proof(action, data):
    return signing.dumps(
        {'action': action, 'data': data},
        key=key_for('assurance'),
        salt='orvia.calendly.rpc.v1',
        compress=True,
    )


def verify(token, actions):
    try:
        value = signing.loads(
            token, key=key_for('assurance'), salt='orvia.calendly.rpc.v1', max_age=120
        )
        if (
            not isinstance(value, dict)
            or set(value) != {'action', 'data'}
            or value['action'] not in actions
            or not isinstance(value['data'], dict)
        ):
            raise ValueError()
        return value['action'], value['data']
    except (signing.BadSignature, ValueError, TypeError, AttributeError):
        raise PermissionDenied('Preuve Calendly invalide ou expirée.') from None


def rpc(base, target, action, data):
    parts = urlsplit(base)
    if (
        parts.scheme not in ('http', 'https')
        or not parts.netloc
        or parts.path
        or parts.query
        or parts.fragment
        or parts.username
        or parts.password
    ):
        raise Unavailable()
    path = '/api/' + target + '/internal/calendly/'
    try:
        with requests.post(
            base + path,
            json={'proof': proof(action, data)},
            headers={'X-Forwarded-Proto': 'https'},
            timeout=(5, 50),
            stream=True,
            allow_redirects=False,
        ) as response:
            if response.status_code != 200:
                raise Unavailable()
            body = response.raw.read(262145, decode_content=True)
            if len(body) > 262144:
                raise Unavailable()
            value = json.loads(body)
            if not isinstance(value, dict):
                raise Unavailable()
            return value
    except (requests.RequestException, ValueError, UnicodeError):
        raise Unavailable() from None
