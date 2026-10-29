"""Single explicit 245 command. No retries, audio or outcome inference.

The caller's softphone only answers by itself when auto-answer is explicitly enabled (_a=Y).
"""

import csv
import io
import re
import secrets
from time import monotonic
import requests
from .directory import URL


def place(username, password, extension, destination, auto_answer=False):
    if (
        not username
        or not password
        or not re.fullmatch(r'[0-9]{1,10}', extension)
        or not re.fullmatch(r'1[2-9][0-9]{2}[2-9][0-9]{6}', destination)
    ):
        return 'unknown'
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
                return 'unknown'
            body = bytearray()
            deadline = monotonic() + 45
            for chunk in response.iter_content(4096):
                body.extend(chunk)
                if len(body) > 4096 or monotonic() > deadline:
                    return 'unknown'
            rows = list(csv.reader(io.StringIO(body.decode('utf-8-sig')), strict=True))
            if len(rows) != 1:
                return 'unknown'
            row = rows[0]
            # Provider confirmed empty correlation slots in Success,ext,TN,,,,,.
            # Bind to this one HTTPS response's exact post and destination instead.
            if (
                len(row) < 4
                or len(row) > 8
                or row[1:3] != [extension, destination]
                or row[3] not in ('', correlation)
                or any(row[4:])
            ):
                return 'unknown'
            return {'Success': 'accepted', 'Failure': 'rejected'}.get(row[0], 'unknown')
    except (requests.RequestException, ValueError, UnicodeError, csv.Error):
        return 'unknown'
