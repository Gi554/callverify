from django.core import signing
from .tickets import key_for

SALT = 'amx.isolation.visit_booking.v1'


def issue_closer(actor, visit, closer, name):
    return signing.dumps(
        {'actor': actor, 'visit': visit, 'closer': closer, 'name': name},
        key=key_for('isolation'),
        salt='amx.isolation.closer.v1',
    )


def verify_closer(token, actor, visit):
    row = signing.loads(
        token, key=key_for('isolation'), salt='amx.isolation.closer.v1', max_age=120
    )
    if (
        not isinstance(row, dict)
        or row.get('actor') != actor
        or row.get('visit') != visit
        or type(row.get('closer')) is not int
        or row['closer'] <= 0
    ):
        raise signing.BadSignature('Invalid closer assignment')
    if not isinstance(row.get('name'), str) or not 1 <= len(row['name']) <= 150:
        raise signing.BadSignature('Invalid closer name')
    return row


def issue_booking(actor, prospect, setter, setter_name, client, client_name):
    return signing.dumps(
        {
            'aud': 'isolation',
            'actor': actor,
            'prospect': prospect,
            'setter': {'id': setter, 'name': setter_name},
            'client': {'id': client, 'name': client_name},
        },
        key=key_for('isolation'),
        salt=SALT,
    )


def verify_booking(token, actor, prospect):
    claims = signing.loads(token, key=key_for('isolation'), salt=SALT, max_age=120)
    if not isinstance(claims, dict) or claims.get('aud') != 'isolation':
        raise signing.BadSignature('Wrong audience')
    for key, value in [('actor', actor), ('prospect', prospect)]:
        if type(claims.get(key)) is not int or claims[key] != value:
            raise signing.BadSignature('Wrong scope')
    for role in ('setter', 'client'):
        person = claims.get(role)
        if not isinstance(person, dict) or type(person.get('id')) is not int or person['id'] <= 0:
            raise signing.BadSignature('Invalid participant')
        if (
            not isinstance(person.get('name'), str)
            or not person['name']
            or len(person['name']) > 150
        ):
            raise signing.BadSignature('Invalid name')
    if claims['setter']['id'] == claims['client']['id']:
        raise signing.BadSignature('Distinct roles required')
    return claims
