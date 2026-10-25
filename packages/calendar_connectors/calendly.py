"""Calendly account discovery only. No booking, invitation or organisation membership writes."""

import base64
import hashlib
import re
import requests
from urllib.parse import urlencode, urlsplit

from .providers import ProviderError, http, instant

SCOPES = ('users:read', 'event_types:read')
BOOKING_SCOPES = (*SCOPES, 'availability:read', 'scheduled_events:write', 'webhooks:write')
API = 'https://api.calendly.com'


def authorization(options, state, verifier):
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    return 'https://auth.calendly.com/oauth/authorize?' + urlencode(
        {
            'client_id': options['client_id'],
            'response_type': 'code',
            'redirect_uri': options['redirect'],
            'scope': ' '.join(BOOKING_SCOPES),
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
        'scopes': scope.split() if isinstance(scope, str) else [],
        'organization': result.get('organization', ''),
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


def times(access, event_type, start, end):
    resource_uri(event_type, 'event_types')
    data = http(
        'GET',
        API + '/event_type_available_times',
        headers={'Authorization': 'Bearer ' + access},
        params={
            'event_type': event_type,
            'start_time': start.isoformat(),
            'end_time': end.isoformat(),
        },
    )
    values = data.get('collection')
    if not isinstance(values, list) or len(values) > 2000:
        raise ProviderError()
    result = set()
    for value in values:
        if not isinstance(value, dict):
            raise ProviderError()
        when = instant(value.get('start_time'))
        if value.get('status') == 'available' and start <= when < end:
            result.add(when.isoformat())
    return sorted(result)


def invitee_uri(value):
    if not isinstance(value, str) or not re.fullmatch(
        re.escape(API) + r'/scheduled_events/[A-Za-z0-9_-]{1,128}/invitees/[A-Za-z0-9_-]{1,128}',
        value,
    ):
        raise ProviderError()
    return value


def create_invitee(access, event_type, start, name, email, request_id):
    resource_uri(event_type, 'event_types')
    try:
        with requests.post(
            API + '/invitees',
            headers={'Authorization': 'Bearer ' + access},
            json={
                'event_type': event_type,
                'start_time': start.isoformat(),
                'invitee': {'name': name, 'email': email, 'timezone': 'America/Toronto'},
                'tracking': {'utm_source': 'orvia', 'utm_content': str(request_id)},
            },
            timeout=15,
            stream=True,
            allow_redirects=False,
        ) as response:
            if response.status_code in (400, 401, 403, 404, 409, 422):
                raise ProviderError(code='rejected')
            if response.status_code != 201:
                raise ProviderError(code='uncertain')
            body = response.raw.read(262145, decode_content=True)
            if len(body) > 262144:
                raise ProviderError(code='uncertain')
            import json

            data = json.loads(body)
            value = data.get('resource')
            if not isinstance(value, dict) or value.get('status') != 'active':
                raise ProviderError(code='uncertain')
            return invitee_uri(value.get('uri'))
    except (requests.RequestException, ValueError, AttributeError, TypeError):
        raise ProviderError(code='uncertain') from None


def appointment(access, uri, owner, event_type):
    """Fetch canonical provider state; only known, validated resource URLs are requested."""
    value = http('GET', invitee_uri(uri), headers={'Authorization': 'Bearer ' + access}).get(
        'resource'
    )
    if (
        not isinstance(value, dict)
        or value.get('uri') != uri
        or value.get('status') not in ('active', 'canceled')
    ):
        raise ProviderError()
    event_uri = resource_uri(value.get('event'), 'scheduled_events')
    event = http('GET', event_uri, headers={'Authorization': 'Bearer ' + access}).get('resource')
    if (
        not isinstance(event, dict)
        or event.get('uri') != event_uri
        or event.get('event_type') != event_type
        or not isinstance(event.get('event_memberships'), list)
        or owner
        not in {
            member.get('user')
            for member in event.get('event_memberships', [])
            if isinstance(member, dict)
        }
    ):
        raise ProviderError()
    first, last = instant(event.get('start_time')), instant(event.get('end_time'))
    if not 0 < (last - first).total_seconds() <= 86400:
        raise ProviderError()
    return {
        'invitee': uri,
        'starts_at': first.isoformat(),
        'ends_at': last.isoformat(),
        'status': 'cancelled' if value['status'] == 'canceled' else 'scheduled',
        'new_invitee': value.get('new_invitee'),
        'old_invitee': value.get('old_invitee'),
        'rescheduled': value.get('rescheduled') is True,
        'email': value.get('email', ''),
        'request_id': value['tracking'].get('utm_content')
        if isinstance(value.get('tracking'), dict)
        else None,
        'cancel_url': booking_url(value['cancel_url']) if value.get('cancel_url') else '',
        'reschedule_url': booking_url(value['reschedule_url'])
        if value.get('reschedule_url')
        else '',
    }


def find_webhook(access, organization, owner, callback):
    resource_uri(organization, 'organizations')
    resource_uri(owner, 'users')
    params = {'organization': organization, 'user': owner, 'scope': 'user', 'count': 100}
    for _ in range(3):
        data = http(
            'GET',
            API + '/webhook_subscriptions',
            headers={'Authorization': 'Bearer ' + access},
            params=dict(params),
        )
        if not isinstance(data.get('collection'), list) or len(data['collection']) > 100:
            raise ProviderError()
        for item in data['collection']:
            if (
                isinstance(item, dict)
                and item.get('callback_url') == callback
                and item.get('user') == owner
                and item.get('organization') == organization
                and item.get('scope') == 'user'
                and item.get('state') == 'active'
                and isinstance(item.get('events'), list)
                and {'invitee.created', 'invitee.canceled'} <= set(item.get('events', []))
            ):
                return resource_uri(item.get('uri'), 'webhook_subscriptions')
        page = data.get('pagination', {})
        if not isinstance(page, dict):
            raise ProviderError()
        token = page.get('next_page_token') if isinstance(page, dict) else None
        if token is None:
            if isinstance(page, dict) and page.get('next_page'):
                raise ProviderError()
            return None
        if (
            not isinstance(token, str)
            or not 1 <= len(token) <= 2048
            or token == params.get('page_token')
        ):
            raise ProviderError()
        params['page_token'] = token
    raise ProviderError()


def create_webhook(access, organization, owner, callback):
    resource_uri(organization, 'organizations')
    resource_uri(owner, 'users')
    try:
        with requests.post(
            API + '/webhook_subscriptions',
            headers={'Authorization': 'Bearer ' + access},
            json={
                'url': callback,
                'events': ['invitee.created', 'invitee.canceled'],
                'organization': organization,
                'user': owner,
                'scope': 'user',
            },
            timeout=15,
            stream=True,
            allow_redirects=False,
        ) as response:
            if response.status_code in (400, 401, 403, 404, 422):
                raise ProviderError(code='rejected')
            if response.status_code != 201:
                raise ProviderError(code='uncertain')
            body = response.raw.read(262145, decode_content=True)
            if len(body) > 262144:
                raise ProviderError(code='uncertain')
            import json

            value = json.loads(body).get('resource')
    except (requests.RequestException, ValueError, AttributeError, TypeError):
        raise ProviderError(code='uncertain') from None
    if (
        not isinstance(value, dict)
        or value.get('callback_url') != callback
        or value.get('scope') != 'user'
        or value.get('user') != owner
        or value.get('organization') != organization
        or value.get('state') != 'active'
    ):
        raise ProviderError()
    return resource_uri(value.get('uri'), 'webhook_subscriptions')
