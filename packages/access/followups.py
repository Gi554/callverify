"""Short-lived, task-bound attestation of an active Assurance setter."""

from django.core import signing
from .tickets import key_for

SALT = 'amx.assurance.follow_up_owner.v1'


def issue_owner(actor_id, task_id, setter_id, setter_name):
    return signing.dumps(
        {
            'aud': 'assurance',
            'actor': actor_id,
            'task': task_id,
            'setter': {'id': setter_id, 'name': setter_name},
        },
        key=key_for('assurance'),
        salt=SALT,
    )


def verify_owner(token, actor_id, task_id):
    claims = signing.loads(token, key=key_for('assurance'), salt=SALT, max_age=120)
    if not isinstance(claims, dict) or claims.get('aud') != 'assurance':
        raise signing.BadSignature('Wrong audience')
    if type(claims.get('actor')) is not int or claims['actor'] != actor_id:
        raise signing.BadSignature('Wrong actor')
    if type(claims.get('task')) is not int or claims['task'] != task_id:
        raise signing.BadSignature('Wrong task')
    setter = claims.get('setter')
    if not isinstance(setter, dict) or type(setter.get('id')) is not int or setter['id'] <= 0:
        raise signing.BadSignature('Invalid setter')
    if not isinstance(setter.get('name'), str) or not setter['name'] or len(setter['name']) > 150:
        raise signing.BadSignature('Invalid name')
    return setter
