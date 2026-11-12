"""Read-only NEWT 511 format inspection. No inferred field mapping or call outcome."""

import csv
import hashlib
import io
import json
import re
import secrets
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from time import monotonic
import requests
from .directory import URL, DirectoryUnavailable

MAX_BYTES = 1024 * 1024
CONFIRMED_COLUMNS = ['From', 'To', 'Description', 'DNID', 'Date', 'Time', 'Duration', 'Amount']
PROVIDER_TIMEZONE = 'America/Toronto'


def confirmed(headings):
    return [value.strip() for value in headings] == CONFIRMED_COLUMNS


def normalize_extension(value):
    """Return the numeric NEWT extension while tolerating CSV whitespace."""
    text = str(value or '').strip()
    return text if re.fullmatch(r'\d{1,8}', text) else ''


def duration_seconds(value):
    """Parse the unambiguous duration spellings returned by NEWT.

    The provider documents the column name but not its unit. Bare integers keep
    the existing seconds interpretation; clock-style values are converted
    exactly and malformed values remain unavailable instead of being guessed.
    """
    text = str(value or '').strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    parts = text.split(':')
    if len(parts) not in (2, 3) or any(not part.isdigit() for part in parts):
        return None
    numbers = [int(part) for part in parts]
    if len(numbers) == 2:
        minutes, seconds = numbers
        if seconds >= 60:
            return None
        return minutes * 60 + seconds
    hours, minutes, seconds = numbers
    if minutes >= 60 or seconds >= 60:
        return None
    return hours * 3600 + minutes * 60 + seconds


def local_instant(day, clock):
    """Do not guess which repeated autumn hour a provider timestamp denotes."""
    try:
        local = datetime.strptime(day + ' ' + clock, '%Y-%m-%d %H:%M:%S')
        zone = ZoneInfo(PROVIDER_TIMEZONE)
        candidates = {
            local.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
            for fold in (0, 1)
            if local.replace(tzinfo=zone, fold=fold)
            .astimezone(timezone.utc)
            .astimezone(zone)
            .replace(tzinfo=None)
            == local
        }
        return next(iter(candidates)).isoformat() if len(candidates) == 1 else None
    except ValueError:
        return None


def parse_records(raw):
    """Confirmed 511 CSV, for scoped matching by the caller; no answer inference."""
    if len(raw) > MAX_BYTES:
        raise DirectoryUnavailable()
    inspect(raw)
    try:
        reader = csv.reader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True)
        if not confirmed(next(reader)):
            raise DirectoryUnavailable()
        records = []
        for row in reader:
            if not row:
                continue
            values = dict(zip(CONFIRMED_COLUMNS, row))
            # Duration and Amount have no confirmed unit/semantics; preserve as text.
            records.append(
                {
                    'from': normalize_extension(values['From']),
                    'to': values['To'].strip(),
                    'description': values['Description'],
                    'dnid': values['DNID'],
                    'local_date': values['Date'],
                    'local_time': values['Time'],
                    'timezone': PROVIDER_TIMEZONE,
                    'occurred_at': local_instant(values['Date'], values['Time']),
                    'duration_raw': values['Duration'],
                    'amount_raw': values['Amount'],
                }
            )
        return records
    except (UnicodeError, csv.Error, StopIteration, ValueError):
        raise DirectoryUnavailable() from None


def inspect(raw):
    try:
        reader = csv.reader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True)
        headings = next(reader)
        if not 2 <= len(headings) <= 64 or any(
            not h.strip()
            or len(h) > 100
            or not any(c.isalpha() for c in h)
            or any(ord(c) < 32 or ord(c) == 127 for c in h)
            for h in headings
        ):
            raise DirectoryUnavailable()
        if len(set(h.strip().casefold() for h in headings)) != len(headings):
            raise DirectoryUnavailable()
        count = 0
        for row in reader:
            if not row:
                continue
            if len(row) != len(headings) or any(len(cell) > 2048 for cell in row):
                raise DirectoryUnavailable()
            count += 1
            if count > 10000:
                raise DirectoryUnavailable()
    except (UnicodeError, csv.Error, StopIteration, ValueError):
        raise DirectoryUnavailable() from None
    return {
        'columns': headings,
        'row_count': count,
        'schema_fingerprint': hashlib.sha256(
            json.dumps(headings, ensure_ascii=False).encode()
        ).hexdigest(),
    }


def shape(cell):
    """Character classes of a cell (digits as 9, letters as a): its format, never its value."""
    return re.sub(r'[^\W\d_]', 'a', re.sub(r'\d', '9', cell))[:30]


def describe(raw):
    """Structure of a 511 body that is safe to log: no number, name or timestamp is kept."""
    result = {'bytes': len(raw)}
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeError:
        return {**result, 'problem': 'encoding'}
    try:
        rows = [row for row in csv.reader(io.StringIO(text, newline='')) if row]
    except csv.Error:
        return {**result, 'problem': 'csv'}
    if not rows:
        return {**result, 'problem': 'empty'}
    widths = {}
    for row in rows[1:]:
        widths[len(row)] = widths.get(len(row), 0) + 1
    return {
        **result,
        'problem': 'format',
        # A first line holding digits may be a call line without headings: only its shape.
        'headings': [
            shape(cell) if any(c.isdigit() for c in cell) else cell[:30] for cell in rows[0][:16]
        ],
        'rows': len(rows) - 1,
        'widths': {str(size): count for size, count in sorted(widths.items())[:5]},
        'first_row_shape': [shape(cell) for cell in rows[1][:16]] if len(rows) > 1 else [],
    }


def unavailable(problem):
    error = DirectoryUnavailable(problem)
    error.diagnostic = {'problem': problem}
    return error


def fetch_schema(username, password, start, end):
    return inspect(fetch_raw(username, password, start, end))


def fetch_records(username, password, start, end):
    raw = fetch_raw(username, password, start, end)
    try:
        return parse_records(raw)
    except DirectoryUnavailable as error:
        error.diagnostic = describe(raw)
        raise


def fetch_raw(username, password, start, end):
    if not username or not password:
        raise unavailable('credentials')
    # Dates are server-validated date objects, never arbitrary provider arguments.
    from datetime import date

    if type(start) is not date or type(end) is not date or end < start or (end - start).days > 6:
        raise unavailable('window')
    try:
        with requests.get(
            URL,
            params={
                '_f': '511',
                '_v': 'C',
                '_sd': start.strftime('%Y%m%d'),
                '_ed': end.strftime('%Y%m%d'),
                '_dir': 'B',
                '_t': secrets.token_hex(5),
            },
            auth=(username, password),
            timeout=(5, 10),
            allow_redirects=False,
            stream=True,
        ) as response:
            if response.status_code != 200:
                raise unavailable(f'http_{response.status_code}')
            body = bytearray()
            deadline = monotonic() + 20
            for chunk in response.iter_content(chunk_size=8192):
                if monotonic() > deadline:
                    raise unavailable('too_slow')
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise unavailable('too_large')
            return bytes(body)
    except (requests.RequestException, ValueError, UnicodeError):
        raise unavailable('network') from None
