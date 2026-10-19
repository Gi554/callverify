import base64
import hashlib
from datetime import timezone
from urllib.parse import urlencode,urlsplit
import requests
from django.utils.dateparse import parse_datetime

GOOGLE_SCOPES=('https://www.googleapis.com/auth/calendar.events','https://www.googleapis.com/auth/calendar.events.freebusy')
MICROSOFT_SCOPES=('offline_access','Calendars.ReadWrite')

class ProviderError(Exception):
    def __init__(self,reauthorize=False):self.reauthorize=reauthorize;super().__init__('Calendar provider unavailable')

def endpoints(provider,tenant='common'):
    if provider=='google':return 'https://accounts.google.com/o/oauth2/v2/auth','https://oauth2.googleapis.com/token',GOOGLE_SCOPES
    return f'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize',f'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token',MICROSOFT_SCOPES

def authorization(provider,config,redirect,state,verifier):
    url,_,scopes=endpoints(provider,config['tenant'])
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    params={'client_id':config['client_id'],'response_type':'code','redirect_uri':redirect,'scope':' '.join(scopes),
        'state':state,'code_challenge':challenge,'code_challenge_method':'S256'}
    if provider=='google':params.update(access_type='offline',prompt='consent')
    else:params.update(response_mode='query',prompt='select_account')
    return url+'?'+urlencode(params)

def http(method,url,**kwargs):
    try:
        response=requests.request(method,url,timeout=10,allow_redirects=False,**kwargs)
        if response.status_code not in (200,201):
            invalid=response.status_code==401
            if response.status_code==400:
                try:invalid=response.json().get('error')=='invalid_grant'
                except (ValueError,AttributeError):pass
            raise ProviderError(invalid)
        if len(response.content)>2_000_000:raise ProviderError()
        data=response.json()
        if not isinstance(data,dict):raise ProviderError()
        return data
    except (requests.RequestException,ValueError):raise ProviderError() from None

def tokens(provider,config,*,code=None,redirect=None,verifier=None,refresh=None):
    _,url,_=endpoints(provider,config['tenant'])
    data={'client_id':config['client_id'],'client_secret':config['client_secret']}
    if refresh:data.update(grant_type='refresh_token',refresh_token=refresh)
    else:data.update(grant_type='authorization_code',code=code,redirect_uri=redirect,code_verifier=verifier)
    if provider=='microsoft':data['scope']=' '.join(MICROSOFT_SCOPES)
    result=http('POST',url,data=data)
    access=result.get('access_token');renew=result.get('refresh_token',refresh);expires=result.get('expires_in')
    if not isinstance(access,str) or not 0<len(access)<=20000 or not isinstance(renew,str) or not 0<len(renew)<=20000:raise ProviderError(True)
    if str(result.get('token_type','')).lower()!='bearer' or type(expires) is not int or not 60<=expires<=604800:raise ProviderError()
    scope=result.get('scope')
    if scope is not None or not refresh:
        if not isinstance(scope,str):raise ProviderError(True)
        granted={value.removeprefix('https://graph.microsoft.com/') for value in scope.split()}
        required=set(GOOGLE_SCOPES if provider=='google' else ('Calendars.ReadWrite',))
        if not required<=granted:raise ProviderError(True)
    return {'access':access,'refresh':renew},expires

def instant(value,utc=False):
    if not isinstance(value,str):raise ProviderError()
    try:result=parse_datetime(value)
    except ValueError:raise ProviderError() from None
    if result is None:raise ProviderError()
    if result.tzinfo is None:
        if not utc:raise ProviderError()
        result=result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)

def busy(provider,access,start,end):
    headers={'Authorization':'Bearer '+access};periods=[]
    if provider=='google':
        data=http('POST','https://www.googleapis.com/calendar/v3/freeBusy',headers=headers,json={'timeMin':start.isoformat(),'timeMax':end.isoformat(),'timeZone':'UTC','items':[{'id':'primary'}]})
        calendars=data.get('calendars')
        if not isinstance(calendars,dict) or len(calendars)!=1:raise ProviderError()
        row=next(iter(calendars.values()))
        if not isinstance(row,dict) or row.get('errors') or not isinstance(row.get('busy'),list):raise ProviderError()
        for item in row['busy']:
            if not isinstance(item,dict):raise ProviderError()
            periods.append((instant(item.get('start')),instant(item.get('end'))))
    else:
        headers['Prefer']='outlook.timezone="UTC"'
        url='https://graph.microsoft.com/v1.0/me/calendar/calendarView'
        params={'startDateTime':start.isoformat(),'endDateTime':end.isoformat(),'$select':'start,end,showAs,isCancelled','$top':1000}
        for _ in range(5):
            data=http('GET',url,headers=headers,params=params);params=None
            events=data.get('value')
            if not isinstance(events,list):raise ProviderError()
            for item in events:
                if not isinstance(item,dict):raise ProviderError()
                if item.get('isCancelled') is True or item.get('showAs')=='free':continue
                first=item.get('start',{});last=item.get('end',{})
                if not isinstance(first,dict) or not isinstance(last,dict) or first.get('timeZone') not in ('UTC','Etc/UTC') or last.get('timeZone') not in ('UTC','Etc/UTC'):raise ProviderError()
                periods.append((instant(first.get('dateTime'),True),instant(last.get('dateTime'),True)))
            url=data.get('@odata.nextLink')
            if not url:break
            if not isinstance(url,str):raise ProviderError()
            parsed=urlsplit(url)
            if parsed.scheme!='https' or parsed.netloc!='graph.microsoft.com' or parsed.path!='/v1.0/me/calendar/calendarView' or parsed.fragment:raise ProviderError()
        else:raise ProviderError()
    # Only intervals leave this adapter. No title, description, attendee or organizer.
    if any(last<=first for first,last in periods):raise ProviderError()
    return [{'start':max(first,start).isoformat(),'end':min(last,end).isoformat()} for first,last in sorted(periods) if first<end and last>start]
