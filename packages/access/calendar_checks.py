"""Service-only assertions; never accepted as session or workspace tickets."""
from datetime import timedelta
from django.core import signing
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .tickets import key_for

def salt(workspace):return f'amx.{workspace}.calendar-check.v1'

def issue(actor,role,owner,start,end,source_id=None,workspace='assurance'):
    return signing.dumps({'aud':workspace,'actor':actor,'role':role,'owner':owner,
        'start':start.isoformat(),'end':end.isoformat(),'source_id':source_id},key=key_for(workspace),salt=salt(workspace))

def verify(token,workspace='assurance'):
    data=signing.loads(token,key=key_for(workspace),salt=salt(workspace),max_age=120)
    if not isinstance(data,dict) or set(data)!={'aud','actor','role','owner','start','end','source_id'}:raise signing.BadSignature('Invalid fields')
    if data['aud']!=workspace or data['role'] not in ('setter','administrator'):raise signing.BadSignature('Invalid audience or role')
    if any(type(data[key]) is not int or data[key]<=0 for key in ('actor','owner')):raise signing.BadSignature('Invalid identity')
    if data['source_id'] is not None and (type(data['source_id']) is not int or data['source_id']<=0):raise signing.BadSignature('Invalid source')
    for key in ('start','end'):
        if not isinstance(data[key],str):raise signing.BadSignature('Invalid interval')
        value=parse_datetime(data[key])
        if value is None or timezone.is_naive(value):raise signing.BadSignature('Invalid interval')
        data[key]=value
    if not timedelta(0)<data['end']-data['start']<=timedelta(days=31):raise signing.BadSignature('Invalid interval')
    return data
