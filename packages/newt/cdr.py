"""Read-only NEWT 511 format inspection. No inferred field mapping or call outcome."""
import csv
import hashlib
import io
import json
import secrets
from time import monotonic
import requests
from .directory import URL,DirectoryUnavailable

MAX_BYTES=1024*1024

def inspect(raw):
    try:
        reader=csv.reader(io.StringIO(raw.decode('utf-8-sig'),newline=''),strict=True)
        headings=next(reader)
        if not 2<=len(headings)<=64 or any(not h.strip() or len(h)>100 or not any(c.isalpha() for c in h) or any(ord(c)<32 or ord(c)==127 for c in h) for h in headings):raise DirectoryUnavailable()
        if len(set(h.strip().casefold() for h in headings))!=len(headings):raise DirectoryUnavailable()
        count=0
        for row in reader:
            if not row:continue
            if len(row)!=len(headings) or any(len(cell)>2048 for cell in row):raise DirectoryUnavailable()
            count+=1
            if count>10000:raise DirectoryUnavailable()
    except (UnicodeError,csv.Error,StopIteration,ValueError):raise DirectoryUnavailable() from None
    return {'columns':headings,'row_count':count,'schema_fingerprint':hashlib.sha256(json.dumps(headings,ensure_ascii=False).encode()).hexdigest()}


def fetch_schema(username,password,start,end):
    if not username or not password:raise DirectoryUnavailable()
    # Dates are server-validated date objects, never arbitrary provider arguments.
    from datetime import date
    if type(start) is not date or type(end) is not date or end<start or (end-start).days>6:raise DirectoryUnavailable()
    try:
        with requests.get(URL,params={'_f':'511','_v':'C','_sd':start.strftime('%Y%m%d'),'_ed':end.strftime('%Y%m%d'),'_dir':'B','_t':secrets.token_hex(5)},auth=(username,password),timeout=(5,10),allow_redirects=False,stream=True) as response:
            if response.status_code!=200:raise DirectoryUnavailable()
            body=bytearray();deadline=monotonic()+20
            for chunk in response.iter_content(chunk_size=8192):
                if monotonic()>deadline:raise DirectoryUnavailable()
                body.extend(chunk)
                if len(body)>MAX_BYTES:raise DirectoryUnavailable()
            return inspect(bytes(body))
    except (requests.RequestException,ValueError,UnicodeError):raise DirectoryUnavailable() from None
