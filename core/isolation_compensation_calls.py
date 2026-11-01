"""Bound, fail-visible call-counter bridge for the administrative report."""

from urllib.parse import urlsplit
import requests
from django.conf import settings
from packages.access.isolation_events import issue


def load(actor, start, end):
    base = settings.PORTAL_INTERNAL_URL.rstrip('/')
    parsed = urlsplit(base)
    if (
        parsed.scheme not in ('http', 'https')
        or not parsed.netloc
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ValueError('Internal URL required')
    claims = {'actor': actor, 'from': str(start), 'to': str(end)}
    with requests.get(
        base + '/api/portal/internal/isolation/call-statistics/',
        params={k: claims[k] for k in ('from', 'to')},
        headers={
            'Authorization': 'Bearer ' + issue('compensation_calls', **claims),
            'X-Forwarded-Proto': 'https',
        },
        timeout=(5, 15),
        allow_redirects=False,
        stream=True,
    ) as response:
        if response.status_code != 200:
            raise ValueError('Call source unavailable')
        import json

        payload = response.raw.read(1000001, decode_content=True)
        if len(payload) > 1000000:
            raise ValueError('Call source too large')
        data = json.loads(payload)
    if (
        not isinstance(data, dict)
        or set(data) != {'from', 'to', 'client', 'results', 'totals'}
        or data['from'] != str(start)
        or data['to'] != str(end)
        or not isinstance(data['results'], list)
        or len(data['results']) > 5000
    ):
        raise ValueError('Invalid call source')
    client = data['client']
    if client is not None and (
        not isinstance(client, dict)
        or set(client) != {'id', 'name'}
        or type(client['id']) is not int
        or client['id'] <= 0
        or not isinstance(client['name'], str)
        or not 1 <= len(client['name']) <= 150
    ):
        raise ValueError('Invalid client')
    seen = set()

    def counts(row):
        if (
            any(
                type(row.get(key)) is not int or row[key] < 0
                for key in ('calls', 'attempts', 'uncertain')
            )
            or row['calls'] + row['uncertain'] > row['attempts']
        ):
            raise ValueError('Invalid counts')

    if not isinstance(data['totals'], dict) or set(data['totals']) != {
        'calls',
        'attempts',
        'uncertain',
    }:
        raise ValueError('Invalid totals')
    counts(data['totals'])
    for row in data['results']:
        if (
            not isinstance(row, dict)
            or set(row) != {'user_id', 'user__username', 'calls', 'attempts', 'uncertain'}
            or type(row['user_id']) is not int
            or row['user_id'] <= 0
            or row['user_id'] in seen
            or not isinstance(row['user__username'], str)
            or not 1 <= len(row['user__username']) <= 150
        ):
            raise ValueError('Invalid user')
        seen.add(row['user_id'])
        counts(row)
    if any(
        sum(row[key] for row in data['results']) != data['totals'][key]
        for key in ('calls', 'attempts', 'uncertain')
    ):
        raise ValueError('Inconsistent counts')
    return data
