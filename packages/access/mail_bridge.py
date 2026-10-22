"""Purpose-specific, short-lived server credentials, separate from user tickets."""

import os
from django.conf import settings
from django.core import signing
from django.core.exceptions import ImproperlyConfigured


def key():
    value = os.getenv('ASSURANCE_MAIL_BRIDGE_KEY', '')
    if not value:
        if not settings.DEBUG:
            raise ImproperlyConfigured('ASSURANCE_MAIL_BRIDGE_KEY required')
        value = 'local-assurance-mail-development-only'
    return value


def issue(operation, **claims):
    return signing.dumps({'op': operation, **claims}, key=key(), salt='amx.assurance.mail.v1')


def verify(token, operation, **claims):
    data = signing.loads(token, key=key(), salt='amx.assurance.mail.v1', max_age=60)
    if data != {'op': operation, **claims}:
        raise signing.BadSignature('Wrong mail operation')
