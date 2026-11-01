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


def issue_booking(
    actor,
    prospect,
    setter,
    setter_name,
    client,
    client_name,
    reactivation=None,
    closer=None,
    followup=None,
):
    return signing.dumps(
        {
            'aud': 'isolation',
            'actor': actor,
            'prospect': prospect,
            'setter': {'id': setter, 'name': setter_name},
            'client': {'id': client, 'name': client_name},
            **({'reactivation': reactivation} if reactivation is not None else {}),
            **({'followup': followup} if followup is not None else {}),
            **({'closer': closer} if closer is not None else {}),
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
    roles = ('setter', 'client') + (('closer',) if 'closer' in claims else ())
    for role in roles:
        person = claims.get(role)
        if not isinstance(person, dict) or type(person.get('id')) is not int or person['id'] <= 0:
            raise signing.BadSignature('Invalid participant')
        if (
            not isinstance(person.get('name'), str)
            or not person['name']
            or len(person['name']) > 150
        ):
            raise signing.BadSignature('Invalid name')
    if len({claims[role]['id'] for role in roles}) != len(roles):
        raise signing.BadSignature('Distinct roles required')
    if 'reactivation' in claims and (
        type(claims['reactivation']) is not int
        or claims['reactivation'] <= 0
        or claims['client']['id'] != actor
    ):
        raise signing.BadSignature('Invalid reactivation')
    if 'followup' in claims and (
        type(claims['followup']) is not int
        or claims['followup'] <= 0
        or claims['client']['id'] != actor
        or 'reactivation' in claims
    ):
        raise signing.BadSignature('Invalid follow-up')
    return claims
