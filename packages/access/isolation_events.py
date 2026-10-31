"""Purpose-bound server messages for Isolation publication and notifications."""

from django.core import signing
from .tickets import key_for


def issue(operation, **claims):
    return signing.dumps(
        {'operation': operation, **claims},
        key=key_for('isolation'),
        salt='orvia.isolation.events.v1',
    )


def verify(token, operation):
    data = signing.loads(
        token, key=key_for('isolation'), salt='orvia.isolation.events.v1', max_age=120
    )
    if not isinstance(data, dict) or data.pop('operation', None) != operation:
        raise signing.BadSignature('Invalid Isolation operation')
    return data
