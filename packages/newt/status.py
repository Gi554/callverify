"""Read-only NEWT function 244. Never originate, hang up or control an existing call."""
import csv
import io
import re
import secrets
from time import monotonic
import requests
from .directory import URL,DirectoryUnavailable

MAX_BYTES=64*1024

def parse(raw,extension,correlation):
    try:
        rows=csv.reader(io.StringIO(raw.decode('utf-8-sig'),newline=''),strict=True)
        codes=[]
        for row in rows:
            if not row:continue
            if len(row)==9 and row[-1]=='':row=row[:-1]
            if len(row)!=8 or len(codes)>=100:raise DirectoryUnavailable()
            if row[0]!=extension or row[4]!=correlation or row[2] not in ('R','C','H'):raise DirectoryUnavailable()
            codes.append(row[2])
    except (UnicodeError,csv.Error,ValueError):raise DirectoryUnavailable() from None
    # No observations never proves a post is free, inactive or invalid.
    return {'codes':sorted(set(codes)),'observations':len(codes),'conclusion':'indeterminate'}


def fetch_status(username,password,extension):
    if not username or not password or not isinstance(extension,str) or not re.fullmatch(r'[0-9]{1,10}',extension):raise DirectoryUnavailable()
    correlation=secrets.token_hex(5)
    try:
        with requests.get(URL,params={'_f':'244','_v':'C','_x':extension,'_t':correlation},auth=(username,password),timeout=(5,10),allow_redirects=False,stream=True) as response:
            if response.status_code!=200:raise DirectoryUnavailable()
            body=bytearray();deadline=monotonic()+20
            for chunk in response.iter_content(chunk_size=8192):
                if monotonic()>deadline:raise DirectoryUnavailable()
                body.extend(chunk)
                if len(body)>MAX_BYTES:raise DirectoryUnavailable()
            return parse(bytes(body),extension,correlation)
    except (requests.RequestException,ValueError,UnicodeError):raise DirectoryUnavailable() from None
