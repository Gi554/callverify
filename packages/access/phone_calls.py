"""Short-lived Assurance call intent, distinct from login and booking tickets."""
from django.core import signing
from .tickets import key_for
SALT='amx.assurance.phone-call.v1'

def issue(actor,contact,revision,request_id,destination,lease):
    return signing.dumps({'aud':'assurance','actor':actor,'contact':contact,'revision':revision,'request_id':str(request_id),'destination':destination,'lease':str(lease)},key=key_for('assurance'),salt=SALT)

def verify(proof,actor):
    value=signing.loads(proof,key=key_for('assurance'),salt=SALT,max_age=60)
    if not isinstance(value,dict) or set(value)!={'aud','actor','contact','revision','request_id','destination','lease'} or value['aud']!='assurance' or value['actor']!=actor:raise signing.BadSignature('Wrong actor or purpose')
    for key in ('actor','contact','revision'):
        if type(value[key]) is not int or value[key] < (0 if key=='revision' else 1):raise signing.BadSignature('Invalid identifiers')
    from uuid import UUID
    import re
    UUID(value['request_id'])
    UUID(value['lease'])
    if not isinstance(value['destination'],str) or not re.fullmatch(r'1[2-9][0-9]{2}[2-9][0-9]{6}',value['destination']):raise signing.BadSignature('Invalid destination')
    return value
