"""Calendly account discovery only. No booking, invitation or organisation membership writes."""

import base64
import hashlib
import re
from urllib.parse import urlencode, urlsplit

from .providers import ProviderError, http

SCOPES = ('users:read', 'event_types:read')
API = 'https://api.calendly.com'


def authorization(options, state, verifier):
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    return 'https://auth.calendly.com/oauth/authorize?' + urlencode(
        {
            'client_id': options['client_id'],
            'response_type': 'code',
            'redirect_uri': options['redirect'],
            'scope': ' '.join(SCOPES),
            'state': state,
            'code_challenge': challenge.rstrip(b'=').decode(),
            'code_challenge_method': 'S256',
        }
    )


def resource_uri(value, kind):
    if not isinstance(value, str) or not re.fullmatch(
        re.escape(API) + '/' + kind + r'/[A-Za-z0-9_-]{1,128}', value
    ):
        raise ProviderError()
    return value


def booking_url(value):
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 for c in value):
        raise ProviderError()
    try:
        parts = urlsplit(value)
    except ValueError:
        raise ProviderError() from None
    if (
        parts.scheme != 'https'
        or parts.netloc != 'calendly.com'
        or not parts.path.strip('/')
        or parts.query
        or parts.fragment
        or '\\' in value
    ):
        raise ProviderError()
    return value


def text(value, maximum=200):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ProviderError()
    return value


def tokens(options, *, code=None, verifier=None, refresh=None):
    if refresh:
        data = {'grant_type': 'refresh_token', 'refresh_token': refresh}
    else:
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': options['redirect'],
            'code_verifier': verifier,
        }
    result = http(
        'POST',
        'https://auth.calendly.com/oauth/token',
        accepted=(200,),
        auth=(options['client_id'], options['client_secret']),
        data=data,
    )
    access = text(result.get('access_token'), 20000)
    renew = text(result.get('refresh_token'), 20000)
    seconds = result.get('expires_in')
    scope = result.get('scope')
    if (
        str(result.get('token_type', '')).lower() != 'bearer'
        or type(seconds) is not int
        or not 60 <= seconds <= 604800
        or (refresh and renew == refresh)
        or (
            scope is not None
            and (not isinstance(scope, str) or not set(SCOPES) <= set(scope.split()))
        )
    ):
        raise ProviderError(True)
    return {
        'access': access,
        'refresh': renew,
        'owner': resource_uri(result.get('owner'), 'users'),
    }, seconds


def profile(access, owner):
    value = http('GET', API + '/users/me', headers={'Authorization': 'Bearer ' + access}).get(
        'resource'
    )
    if not isinstance(value, dict) or resource_uri(value.get('uri'), 'users') != owner:
        raise ProviderError(True)
    return {
        'uri': owner,
        'name': text(value.get('name')),
        'scheduling_url': booking_url(value.get('scheduling_url')),
    }


def event_types(access, owner):
    resource_uri(owner, 'users')
    params = {'user': owner, 'active': 'true', 'count': 100, 'sort': 'name:asc'}
    result, seen = [], set()
    for _ in range(3):
        data = http(
            'GET',
            API + '/event_types',
            headers={'Authorization': 'Bearer ' + access},
            params=dict(params),
        )
        values = data.get('collection')
        pagination = data.get('pagination')
        if not isinstance(values, list) or len(values) > 100 or not isinstance(pagination, dict):
            raise ProviderError()
        for value in values:
            if not isinstance(value, dict):
                raise ProviderError()
            # This first connector exposes personal solo pages only, never team/round-robin pages.
            if value.get('active') is not True or value.get('kind') != 'solo':
                continue
            entry_profile = value.get('profile', {})
            if not isinstance(entry_profile, dict) or entry_profile.get('owner') != owner:
                continue
            uri = resource_uri(value.get('uri'), 'event_types')
            duration = value.get('duration')
            if uri in seen or type(duration) is not int or not 1 <= duration <= 1440:
                raise ProviderError()
            seen.add(uri)
            result.append(
                {
                    'uri': uri,
                    'name': text(value.get('name')),
                    'duration': duration,
                    'scheduling_url': booking_url(value.get('scheduling_url')),
                }
            )
        token = pagination.get('next_page_token')
        if token is None:
            if pagination.get('next_page'):
                raise ProviderError()
            return result
        if (
            not isinstance(token, str)
            or not 1 <= len(token) <= 2048
            or token == params.get('page_token')
        ):
            raise ProviderError()
        # Never follow next_page URLs supplied by the provider.
        params['page_token'] = token
    raise ProviderError(code='too_many_event_types')
