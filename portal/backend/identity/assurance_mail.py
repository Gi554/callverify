"""Pull minimal business events over HTTP; never connect to the Assurance database."""
from datetime import timedelta
from urllib.parse import urlsplit
import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from packages.access.mail_bridge import issue
from .models import Membership,AssuranceMailRelay,AssuranceMailCursor

def fetch(path,operation,**claims):
    base=settings.ASSURANCE_INTERNAL_URL.rstrip('/')
    parsed=urlsplit(base)
    if parsed.scheme not in ('http','https') or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Configure ASSURANCE_INTERNAL_URL')
    response=requests.get(base+path,headers={'Authorization':'Bearer '+issue(operation,**claims)},timeout=5,allow_redirects=False)
    if response.status_code!=200:raise RuntimeError('Assurance mail bridge unavailable')
    return response.json()

def eligible(event,user):
    data=fetch(f'/api/assurance/internal/mail-events/{event}/{user}/','eligible',event=event,user=user)
    if type(data.get('eligible')) is not bool:raise ValueError('Invalid bridge response')
    return data['eligible']

def sync():
    from .mail_queue import enqueue
    from .recovery import public_url
    cursor,_=AssuranceMailCursor.objects.get_or_create(pk=1)
    data=fetch(f'/api/assurance/internal/mail-events/?after={cursor.after_id}','events',after=cursor.after_id)
    events=data.get('events')
    if not isinstance(events,list) or len(events)>100:raise ValueError('Invalid event batch')
    prepared=[];previous=cursor.after_id
    for event in events:
        event_id=event.get('id');user_id=event.get('setter_id')
        if type(event_id) is not int or not previous<event_id<=9223372036854775807 or type(user_id) is not int or not 0<user_id<=9223372036854775807:raise ValueError('Invalid event identity')
        created=parse_datetime(event.get('created_at',''))
        if created is None or timezone.is_naive(created):raise ValueError('Invalid event date')
        prepared.append((event_id,user_id,created));previous=event_id
    counts={'queued':0,'already_queued':0,'skipped':0}
    for event_id,user_id,created in prepared:
        with transaction.atomic():
            user=get_user_model().objects.filter(pk=user_id,is_active=True).first()
            if not user or not Membership.objects.filter(user=user,workspace='assurance',role='setter',active=True).exists():counts['skipped']+=1;continue
            try:validate_email(user.email)
            except ValidationError:counts['skipped']+=1;continue
            if get_user_model().objects.filter(email__iexact=user.email,is_active=True).count()!=1 or not timezone.now()-timedelta(days=7)<created<=timezone.now()+timedelta(minutes=1):counts['skipped']+=1;continue
            relay,new=AssuranceMailRelay.objects.get_or_create(event_id=event_id,recipient_id=user_id)
            if not new:counts['already_queued']+=1;continue
            relay.mail=enqueue(user=user,workspace='assurance',subject='AMX Assurance — Un suivi nécessite votre attention',
                body=f'Un signalement nécessite votre suivi dans AMX Assurance.\nConnectez-vous au CRM pour consulter vos notifications et traiter vos tâches.\n\n{public_url()}/crm\n\nLa lecture de cet e-mail ne clôture aucune tâche.',
                recipient=user.email,guard={'kind':'assurance_follow_up','event':event_id,'user':user_id},expires_at=created+timedelta(days=7))
            relay.save(update_fields=['mail']);counts['queued']+=1
    AssuranceMailCursor.objects.filter(pk=1,after_id=cursor.after_id).update(after_id=previous if len(events)==100 else 0)
    return counts
