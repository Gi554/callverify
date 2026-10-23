"""Short-lived Assurance call intent, distinct from login and booking tickets."""

from django.core import signing
from .tickets import key_for

SALT = 'amx.assurance.phone-call.v1'


def issue(
    actor, contact, revision, request_id, destination, lease=None, workspace='assurance', label=''
):
    value = {
        'aud': workspace,
        'actor': actor,
        'contact': contact,
        'revision': revision,
        'request_id': str(request_id),
        'destination': destination,
        # Display name signed by the business service, kept for the call history.
        'label': str(label or '')[:120],
    }
    if workspace == 'assurance':
        value['lease'] = str(lease)
    return signing.dumps(value, key=key_for(workspace), salt=f'amx.{workspace}.phone-call.v1')


def verify(proof, actor, workspace='assurance'):
    value = signing.loads(
        proof, key=key_for(workspace), salt=f'amx.{workspace}.phone-call.v1', max_age=60
    )
    fields = {'aud', 'actor', 'contact', 'revision', 'request_id', 'destination', 'label'} | (
        {'lease'} if workspace == 'assurance' else set()
    )
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or value['aud'] != workspace
        or value['actor'] != actor
    ):
        raise signing.BadSignature('Wrong actor or purpose')
    for key in ('actor', 'contact', 'revision'):
        if type(value[key]) is not int or value[key] < (0 if key == 'revision' else 1):
            raise signing.BadSignature('Invalid identifiers')
    from uuid import UUID
    import re

    UUID(value['request_id'])
    if workspace == 'assurance':
        UUID(value['lease'])
    if not isinstance(value['destination'], str) or not re.fullmatch(
        r'1[2-9][0-9]{2}[2-9][0-9]{6}', value['destination']
    ):
        raise signing.BadSignature('Invalid destination')
    if not isinstance(value['label'], str) or len(value['label']) > 120:
        raise signing.BadSignature('Invalid label')
    return value
