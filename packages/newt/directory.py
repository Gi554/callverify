"""NEWT revision 3: ONLY function 343. No generic function selector or call control."""

import csv
import io
import re
import secrets
from time import monotonic
import requests

URL = 'https://newtapi.fibernetics.ca/cgi-bin/fnpapi'
MAX_BYTES = 256 * 1024


class DirectoryUnavailable(Exception):
    pass


def parse(raw):
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise DirectoryUnavailable() from None
    rows = []
    seen = set()
    try:
        for row in csv.reader(io.StringIO(text, newline=''), strict=True):
            if not row or (len(row) == 1 and not row[0].strip()):
                continue
            if len(rows) >= 2000 or len(row) != 3:
                raise DirectoryUnavailable()
            extension, _, name = row
            if (
                not re.fullmatch(r'[0-9]{1,10}', extension)
                or extension in seen
                or len(name) > 150
                or any(ord(c) < 32 or ord(c) == 127 for c in name)
            ):
                raise DirectoryUnavailable()
            seen.add(extension)
            rows.append({'extension': extension, 'name': name})
    except (csv.Error, ValueError):
        raise DirectoryUnavailable() from None
    # Empty or error body is not proof the PBX has no posts.
    if not rows:
        raise DirectoryUnavailable()
    return sorted(rows, key=lambda row: (int(row['extension']), row['extension']))


def fetch(username, password):
    if not username or not password:
        raise DirectoryUnavailable()
    try:
        with requests.get(
            URL,
            params={'_f': '343', '_v': 'C', '_t': secrets.token_hex(5)},
            auth=(username, password),
            timeout=(5, 10),
            allow_redirects=False,
            stream=True,
        ) as response:
            if response.status_code != 200:
                raise DirectoryUnavailable()
            body = bytearray()
            deadline = monotonic() + 20
            for chunk in response.iter_content(chunk_size=8192):
                if monotonic() > deadline:
                    raise DirectoryUnavailable()
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise DirectoryUnavailable()
            return parse(bytes(body))
    except (requests.RequestException, ValueError, UnicodeError):
        raise DirectoryUnavailable() from None
