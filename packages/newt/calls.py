"""Single explicit 245 command. No retries, audio or outcome inference.

The caller's softphone only answers by itself when auto-answer is explicitly enabled (_a=Y).
"""

import csv
import io
import logging
import re
import secrets
from time import monotonic
import requests
from .directory import URL

logger = logging.getLogger(__name__)


def _unknown(reason, response=None, response_bytes=None, csv_rows=None):
    """Log a safe reason for an indeterminate command without logging call data."""
    status = getattr(response, 'status_code', '-') if response is not None else '-'
    content_type = '-'
    if response is not None:
        headers = getattr(response, 'headers', {})
        raw_type = headers.get('Content-Type', '') if hasattr(headers, 'get') else ''
        if isinstance(raw_type, str) and re.fullmatch(r'[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+', raw_type):
            content_type = raw_type.lower()
        else:
            content_type = 'other' if raw_type else 'missing'
    logger.warning(
        'NEWT 245 command indeterminate reason=%s http_status=%s content_type=%s response_bytes=%s csv_row_count=%s csv_row_widths=%s',
        reason,
        status,
        content_type,
        response_bytes if response_bytes is not None else '-',
        len(csv_rows) if csv_rows is not None else '-',
        ','.join(str(len(row)) for row in csv_rows[:5]) if csv_rows is not None else '-',
    )
    return 'unknown'


def place(username, password, extension, destination, auto_answer=False):
    if (
        not username
        or not password
        or not re.fullmatch(r'[0-9]{1,10}', extension)
        or not re.fullmatch(r'1[2-9][0-9]{2}[2-9][0-9]{6}', destination)
    ):
        return _unknown('invalid_input')
    correlation = secrets.token_hex(5)
    params = {
        '_f': '245',
        '_x': extension,
        '_d': destination,
        '_o': '30',
        '_t': correlation,
        '_v': 'C',
    }
    if auto_answer:
        params['_a'] = 'Y'
    try:
        with requests.get(
            URL,
            params=params,
            auth=(username, password),
            timeout=(5, 40),
            allow_redirects=False,
            stream=True,
        ) as response:
            if response.status_code != 200:
                return _unknown('http_status', response)
            body = bytearray()
            deadline = monotonic() + 45
            for chunk in response.iter_content(4096):
                body.extend(chunk)
                if len(body) > 4096:
                    return _unknown('response_too_large', response, len(body))
                if monotonic() > deadline:
                    return _unknown('response_read_deadline', response, len(body))
            rows = [
                row
                for row in csv.reader(
                    io.StringIO(body.decode('utf-8-sig'), newline=''), strict=True
                )
                if row and any(field.strip() for field in row)
            ]
            if len(rows) != 1:
                return _unknown('unexpected_row_count', response, len(body), rows)
            row = rows[0]
            # Provider confirmed empty correlation slots in Success,ext,TN,,,,,.
            # Bind to this one HTTPS response's exact post and destination instead.
            if len(row) < 4 or len(row) > 8:
                return _unknown('unexpected_column_count', response, len(body))
            if row[1] != extension:
                return _unknown('extension_mismatch', response, len(body))
            if row[2] != destination:
                return _unknown('destination_mismatch', response, len(body))
            if row[3] not in ('', correlation):
                return _unknown('correlation_mismatch', response, len(body))
            if any(row[4:]):
                return _unknown('unexpected_extra_fields', response, len(body))
            result = {'Success': 'accepted', 'Failure': 'rejected'}.get(row[0])
            if result is None:
                return _unknown('unrecognized_provider_status', response, len(body))
            return result
    except requests.Timeout:
        return _unknown('request_timeout')
    except requests.RequestException as error:
        return _unknown('request_error_' + type(error).__name__)
    except UnicodeError:
        return _unknown('response_encoding')
    except csv.Error:
        return _unknown('malformed_csv')
    except ValueError:
        return _unknown('invalid_response')
