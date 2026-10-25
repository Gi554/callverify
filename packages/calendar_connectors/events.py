"""Manage only marked AMX events, never invite attendees or touch arbitrary events."""

from datetime import datetime, time, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from .providers import http, busy, instant, ProviderError

GOOGLE = 'https://www.googleapis.com/calendar/v3/calendars/primary/events'
MICROSOFT = 'https://graph.microsoft.com/v1.0/me/calendar/events'
PROPERTY = 'String {07dd3a9a-a2bd-4a21-9125-55cb21ccab25} Name AMXSyncKey'


def headers(access):
    return {
        'Authorization': 'Bearer ' + access,
        'Prefer': 'IdType="ImmutableId", outlook.timezone="UTC"',
    }


def find(provider, access, key):
    if provider == 'google':
        row = http(
            'GET', GOOGLE + '/a' + key.hex, headers=headers(access), accepted=(200, 404, 410)
        )
        if row.get('_status') in (404, 410) or row.get('status') == 'cancelled':
            return None
        properties = row.get('extendedProperties')
        private = properties.get('private') if isinstance(properties, dict) else None
        if not isinstance(private, dict) or private.get('amxSync') != str(key):
            raise ProviderError(code='event_changed')
    else:
        result = http(
            'GET',
            MICROSOFT,
            headers=headers(access),
            params={
                '$filter': f"singleValueExtendedProperties/Any(ep: ep/id eq '{PROPERTY}' and ep/value eq '{key}')",
                '$select': 'id,attendees,changeKey,start,end',
                '$top': 2,
            },
        )
        rows = result.get('value')
        if not isinstance(rows, list) or len(rows) > 1 or result.get('@odata.nextLink'):
            raise ProviderError(code='event_changed')
        if not rows:
            return None
        row = rows[0]
    if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id']:
        raise ProviderError()
    if row.get('attendees'):
        raise ProviderError(code='event_has_attendees')
    return row


def interval(provider, remote):
    result = []
    for key in ('start', 'end'):
        part = remote.get(key)
        if not isinstance(part, dict) or not part.get('dateTime'):
            raise ProviderError(code='event_changed')
        if provider == 'microsoft' and part.get('timeZone') not in ('UTC', 'Etc/UTC'):
            raise ProviderError(code='event_changed')
        result.append(instant(part['dateTime'], utc=provider == 'microsoft'))
    return tuple(result)


def body(provider, key, workspace, source):
    title = (
        f'Orvia {"Assurance" if workspace=="assurance" else "Isolation"} — Rendez-vous {source["id"]}'
    )
    first = source['starts_at'].astimezone(timezone.utc).isoformat()
    last = source['ends_at'].astimezone(timezone.utc).isoformat()
    if provider == 'google':
        return {
            'summary': title,
            'visibility': 'private',
            'transparency': 'opaque',
            'description': 'Consultez Orvia pour les informations du dossier.',
            'start': {'dateTime': first, 'timeZone': 'UTC'},
            'end': {'dateTime': last, 'timeZone': 'UTC'},
            'reminders': {'useDefault': False},
            'extendedProperties': {'private': {'amxSync': str(key)}},
        }
    return {
        'subject': title,
        'sensitivity': 'private',
        'showAs': 'busy',
        'isReminderOn': False,
        'body': {
            'contentType': 'text',
            'content': 'Consultez Orvia pour les informations du dossier.',
        },
        'start': {'dateTime': first, 'timeZone': 'UTC'},
        'end': {'dateTime': last, 'timeZone': 'UTC'},
    }


def publish(provider, access, key, workspace, source, remote):
    if busy(
        provider,
        access,
        source['starts_at'],
        source['ends_at'],
        exclude_id=remote['id'] if remote else None,
    ):
        raise ProviderError(code='slot_busy')
    payload = body(provider, key, workspace, source)
    extra = headers(access)
    if remote:
        etag = remote.get('etag') or remote.get('@odata.etag')
        if not isinstance(etag, str) or not etag:
            raise ProviderError(code='event_changed')
        extra['If-Match'] = etag
        url = (GOOGLE if provider == 'google' else MICROSOFT) + '/' + quote(remote['id'], safe='')
        row = http(
            'PATCH',
            url,
            headers=extra,
            json=payload,
            **({'params': {'sendUpdates': 'none'}} if provider == 'google' else {}),
        )
    else:
        if provider == 'google':
            payload['id'] = 'a' + key.hex
        else:
            payload.update(
                transactionId=str(key),
                singleValueExtendedProperties=[{'id': PROPERTY, 'value': str(key)}],
            )
        row = http(
            'POST',
            GOOGLE if provider == 'google' else MICROSOFT,
            headers=extra,
            json=payload,
            **({'params': {'sendUpdates': 'none'}} if provider == 'google' else {}),
        )
    if not isinstance(row.get('id'), str) or not row['id']:
        raise ProviderError()
    return row['id']


def remove(provider, access, remote):
    if remote is None:
        return
    extra = headers(access)
    etag = remote.get('etag') or remote.get('@odata.etag')
    if not isinstance(etag, str) or not etag:
        raise ProviderError(code='event_changed')
    extra['If-Match'] = etag
    http(
        'DELETE',
        (GOOGLE if provider == 'google' else MICROSOFT) + '/' + quote(remote['id'], safe=''),
        headers=extra,
        accepted=(200, 204, 404, 410),
        **({'params': {'sendUpdates': 'none'}} if provider == 'google' else {}),
    )


def google_busy_except(access, start, end, exclude_id):
    params = {
        'timeMin': start.isoformat(),
        'timeMax': end.isoformat(),
        'singleEvents': 'true',
        'maxResults': 2500,
        'showDeleted': 'false',
        'fields': 'timeZone,nextPageToken,items(id,status,transparency,start,end)',
    }
    periods = []
    for _ in range(5):
        data = http('GET', GOOGLE, headers=headers(access), params=params)
        rows = data.get('items', [])
        if not isinstance(rows, list):
            raise ProviderError()
        for row in rows:
            if not isinstance(row, dict):
                raise ProviderError()
            if (
                row.get('id') == exclude_id
                or row.get('status') == 'cancelled'
                or row.get('transparency') == 'transparent'
            ):
                continue
            values = []
            for key in ('start', 'end'):
                part = row.get(key, {})
                if not isinstance(part, dict):
                    raise ProviderError()
                if part.get('dateTime'):
                    value = instant(part['dateTime'])
                else:
                    try:
                        value = datetime.combine(
                            datetime.strptime(part['date'], '%Y-%m-%d').date(),
                            time.min,
                            ZoneInfo(part.get('timeZone') or data['timeZone']),
                        ).astimezone(timezone.utc)
                    except (KeyError, ValueError, TypeError, ZoneInfoNotFoundError):
                        raise ProviderError() from None
                values.append(value)
            first, last = values
            if last <= first:
                raise ProviderError()
            if first < end and last > start:
                periods.append(
                    {'start': max(first, start).isoformat(), 'end': min(last, end).isoformat()}
                )
        token = data.get('nextPageToken')
        if not token:
            return periods
        if not isinstance(token, str) or len(token) > 10000:
            raise ProviderError()
        params['pageToken'] = token
    raise ProviderError()
