"""Automatic NEWT SMS copies of Assurance alerts for configured team mobiles."""

import secrets
from uuid import NAMESPACE_URL, uuid5

from django.conf import settings
from django.utils.crypto import salted_hmac

from packages.newt import sms
from .isolation_sms import destination
from .models import ReminderPhone, SmsAttempt
from .newt_sms import configured


def _message(stream, event):
    if stream == 'reminders' and event.get('kind') == 'report_missing':
        prospect = str(event.get('prospect_name') or 'un prospect')
        return f'Orvia Assurance : le compte rendu du rendez-vous avec {prospect} n’est pas encore renseigné. Consultez votre espace ORVIA.'
    if stream == 'escalations':
        return 'Orvia Assurance : une alerte nécessite votre supervision. Consultez votre espace ORVIA.'
    return 'Orvia Assurance : une alerte nécessite votre attention. Consultez votre espace ORVIA.'


def send_alert(stream, event_id, user, event):
    """Send once per alert and recipient; an empty mobile simply skips it."""
    if not configured() or not settings.NEWT_SMS_AUTOMATIC_FROM:
        return False
    row = ReminderPhone.objects.filter(user=user).first()
    phone = destination(row.mobile) if row else None
    if phone is None:
        return False
    identifier = uuid5(NAMESPACE_URL, f'orvia/assurance/sms/{stream}/{event_id}/{user.pk}')
    if SmsAttempt.objects.filter(pk=identifier).exists():
        return False
    message = _message(stream, event)
    caller_id = settings.NEWT_SMS_CALLER_ID
    attempt, created = SmsAttempt.objects.get_or_create(
        pk=identifier,
        defaults={
            'actor': user,
            'kind': 'assurance_alert',
            'correlation': secrets.token_hex(5),
            'destination': phone,
            'caller_id': caller_id,
            'fingerprint': salted_hmac(
                'newt-sms-v1', phone + ':' + message, algorithm='sha256'
            ).hexdigest(),
        },
    )
    if not created:
        return False
    try:
        attempt.state = sms.send(
            settings.NEWT_USERNAME,
            settings.NEWT_PASSWORD,
            phone,
            caller_id,
            message,
            attempt.correlation,
        )
    except Exception:
        attempt.state = 'failed'
    attempt.save(update_fields=['state'])
    return True
