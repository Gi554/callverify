from django.core import signing
from .tickets import key_for

SALT = 'amx.isolation.prospect_owner.v1'


def issue_owner(actor, prospect, setter, name):
    return signing.dumps(
        {'aud': 'isolation', 'actor': actor, 'prospect': prospect, 'setter': setter, 'name': name},
        key=key_for('isolation'),
        salt=SALT,
    )


def verify_owner(token, actor, prospect):
    data = signing.loads(token, key=key_for('isolation'), salt=SALT, max_age=120)
    if not isinstance(data, dict) or data.get('aud') != 'isolation':
        raise signing.BadSignature('Wrong audience')
    for field, expected in [('actor', actor), ('prospect', prospect)]:
        if type(data.get(field)) is not int or data[field] != expected:
            raise signing.BadSignature('Wrong scope')
    if type(data.get('setter')) is not int or data['setter'] <= 0:
        raise signing.BadSignature('Invalid setter')
    if not isinstance(data.get('name'), str) or not data['name'] or len(data['name']) > 150:
        raise signing.BadSignature('Invalid name')
    return data


LOT_SALT = 'amx.isolation.setter_lot.v1'


def issue_lot(actor, setter, name):
    return signing.dumps(
        {'aud': 'isolation', 'actor': actor, 'setter': setter, 'name': name},
        key=key_for('isolation'),
        salt=LOT_SALT,
    )


def verify_lot(token, actor):
    data = signing.loads(token, key=key_for('isolation'), salt=LOT_SALT, max_age=120)
    if not isinstance(data, dict) or data.get('aud') != 'isolation':
        raise signing.BadSignature('Wrong audience')
    if type(data.get('actor')) is not int or data['actor'] != actor:
        raise signing.BadSignature('Wrong scope')
    if type(data.get('setter')) is not int or data['setter'] <= 0:
        raise signing.BadSignature('Invalid setter')
    if not isinstance(data.get('name'), str) or not data['name'] or len(data['name']) > 150:
        raise signing.BadSignature('Invalid name')
    return data
