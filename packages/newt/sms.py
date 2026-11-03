"""Explicit NEWT 261 SMS submission and response correlation."""

import csv
import io
from time import monotonic

import requests

from .directory import URL


def send(username, password, destination, caller_id, message, correlation):
    try:
        with requests.post(
            URL,
            data={
                '_f': '261',
                '_tn': destination,
                '_cid': caller_id,
                '_txt': message,
                '_t': correlation,
            },
            auth=(username, password),
            timeout=(5, 25),
            allow_redirects=False,
            stream=True,
        ) as response:
            if response.status_code != 200:
                return 'unknown'
            body = bytearray()
            deadline = monotonic() + 30
            for chunk in response.iter_content(4096):
                body.extend(chunk)
                if len(body) > 4096 or monotonic() > deadline:
                    return 'unknown'
            rows = list(csv.reader(io.StringIO(body.decode('utf-8-sig')), strict=True))
            if len(rows) != 1 or len(rows[0]) != 7:
                return 'unknown'
            status, tn, cid, returned_id, *reserved = rows[0]
            # The live PBX also echoes CID before TN. Require both exact numbers and _t.
            matches_pair = (tn, cid) in ((destination, caller_id), (caller_id, destination))
            if not matches_pair or returned_id != correlation or any(reserved):
                return 'unknown'
            return {'Success': 'accepted', 'Failure': 'rejected'}.get(status, 'unknown')
    except (requests.RequestException, ValueError, csv.Error):
        return 'unknown'
