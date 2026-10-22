"""Read-only history proof, deliberately incompatible with call authorization."""
import re
from django.core import signing
from .tickets import key_for

def number(raw):
    if not isinstance(raw,str) or not re.fullmatch(r'\+?[0-9 ().-]+',raw):raise ValueError('Numéro nord-américain requis.')
    digits=re.sub(r'[^0-9]','',raw)
    if len(digits)==10:digits='1'+digits
    if not re.fullmatch(r'1[2-9][0-9]{2}[2-9][0-9]{6}',digits):raise ValueError('Numéro nord-américain requis.')
    return digits

def issue(actor,resource,revision,destination,workspace):
    return signing.dumps({'actor':actor,'resource':resource,'revision':revision,'destination':destination,'workspace':workspace},
        key=key_for(workspace),salt=f'amx.{workspace}.phone-history.v1')

def verify(token,actor,workspace):
    data=signing.loads(token,key=key_for(workspace),salt=f'amx.{workspace}.phone-history.v1',max_age=60)
    if not isinstance(data,dict) or set(data)!={'actor','resource','revision','destination','workspace'} or data['actor']!=actor or data['workspace']!=workspace:
        raise signing.BadSignature('Wrong history scope')
    for key in ('actor','resource','revision'):
        if type(data[key]) is not int or data[key]<(0 if key=='revision' else 1):raise signing.BadSignature('Invalid history scope')
    if number(data['destination'])!=data['destination']:raise signing.BadSignature('Invalid number')
    return data
