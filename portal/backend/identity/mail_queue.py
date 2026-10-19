"""Durable encrypted mail outbox. SMTP is at-least-once, never exactly-once."""
import base64
import hashlib
import json
import uuid
from datetime import timedelta
from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q,F
from django.utils import timezone
from .models import PortalMail,AccessAudit,Invitation,Membership

def cipher():
    key=settings.PORTAL_MAIL_KEY
    if not key:
        if not settings.DEBUG:raise ImproperlyConfigured('PORTAL_MAIL_KEY required')
        key=base64.urlsafe_b64encode(hashlib.sha256(('portal-mail:'+settings.SECRET_KEY).encode()).digest())
    return Fernet(key)

def enqueue(*,user,workspace='',subject,body,recipient,guard,expires_at):
    payload=cipher().encrypt(json.dumps({'subject':subject,'body':body,'recipient':recipient,'guard':guard},ensure_ascii=False).encode()).decode()
    with transaction.atomic():
        row=PortalMail.objects.create(user=user,workspace=workspace,payload=payload,expires_at=expires_at,next_attempt_at=timezone.now())
        AccessAudit.objects.create(user=user,workspace=workspace,action='mail.queued',metadata={'mail':str(row.pk)})
    return row

def eligible(guard,recipient):
    if guard['kind'] in ('assurance_follow_up','assurance_reminder'):
        from .assurance_mail import eligible as source_eligible
        user=get_user_model().objects.filter(pk=guard['user'],is_active=True,email=recipient).first()
        role=guard.get('role','setter') if guard['kind']=='assurance_reminder' else 'setter'
        if role not in ('setter','advisor'):return False
        if not user or not Membership.objects.filter(user=user,workspace='assurance',role=role,active=True).exists():return False
        if get_user_model().objects.filter(email__iexact=recipient,is_active=True).count()!=1:return False
        return source_eligible(guard['event'],user.pk,stream='reminders') if guard['kind']=='assurance_reminder' else source_eligible(guard['event'],user.pk)
    if guard['kind']=='invitation':
        row=Invitation.objects.select_related('issuer').filter(pk=guard['id']).first()
        return bool(row and not row.accepted_at and not row.revoked_at and row.expires_at>timezone.now()
            and row.token_hash==guard['hash'] and row.email==recipient and row.issuer.is_active
            and Membership.objects.filter(user_id=row.issuer_id,workspace=row.workspace,active=True,role='administrator').exists())
    if guard['kind']=='recovery':
        user=get_user_model().objects.filter(pk=guard['user'],is_active=True).first()
        return bool(user and user.email==recipient and get_user_model().objects.filter(email__iexact=recipient,is_active=True).count()==1
            and default_token_generator.check_token(user,guard['token']))
    return False

def claim_next():
    now=timezone.now()
    due=(Q(status='pending',next_attempt_at__lte=now)|Q(status='sending',lease_until__lte=now))
    for pk in PortalMail.objects.filter(due).order_by('next_attempt_at','created_at').values_list('pk',flat=True)[:100]:
        claim=uuid.uuid4()
        if PortalMail.objects.filter(due,pk=pk).update(status='sending',claim=claim,lease_until=now+timedelta(seconds=60),attempts=F('attempts')+1):
            return PortalMail.objects.get(pk=pk,claim=claim)
    return None

def dispatch(limit=100):
    counts={'sent':0,'retry':0,'failed':0,'expired':0}
    for _ in range(limit):
        row=claim_next()
        if row is None:break
        status='expired'
        try:
            if row.expires_at>timezone.now():
                payload=json.loads(cipher().decrypt(row.payload.encode()))
                if eligible(payload['guard'],payload['recipient']):
                    if row.attempts>5:status='failed'
                    else:
                        sent=send_mail(payload['subject'],payload['body'],settings.DEFAULT_FROM_EMAIL,[payload['recipient']],fail_silently=False)
                        if not sent:raise RuntimeError('No delivery accepted')
                        status='sent'
        except Exception:
            # SMTP/decryption exceptions can contain credentials or tokens: do not log.
            status='failed' if row.attempts>=5 else 'retry'
        with transaction.atomic():
            values={'status':'pending' if status=='retry' else status,'lease_until':None,'claim':None}
            if status=='retry':values['next_attempt_at']=timezone.now()+timedelta(seconds=60*2**(row.attempts-1))
            else:values.update(payload='',finished_at=timezone.now())
            if PortalMail.objects.filter(pk=row.pk,status='sending',claim=row.claim).update(**values):
                AccessAudit.objects.create(user_id=row.user_id,workspace=row.workspace,action='mail.'+status,metadata={'mail':str(row.pk),'attempt':row.attempts})
                counts[status]+=1
    return counts
