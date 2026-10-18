"""Portal attestation of an active Assurance setter/advisor pair.

Separate purpose/salt from login tickets. Assurance owns business associations;
it never reads the central account database.
"""
from django.core import signing
from .tickets import key_for

SALT='amx.assurance.assignment.v1'

def issue_assignment(actor_id,setter_id,setter_name,advisor_id,advisor_name):
    return signing.dumps({'aud':'assurance','actor':actor_id,
        'setter':{'id':setter_id,'name':setter_name},'advisor':{'id':advisor_id,'name':advisor_name}},
        key=key_for('assurance'),salt=SALT)

def verify_assignment(token,actor_id):
    claims=signing.loads(token,key=key_for('assurance'),salt=SALT,max_age=120)
    if not isinstance(claims,dict) or claims.get('aud')!='assurance' or type(claims.get('actor')) is not int or claims['actor']!=actor_id:
        raise signing.BadSignature('Wrong actor or audience')
    for role in ('setter','advisor'):
        person=claims.get(role)
        if not isinstance(person,dict) or type(person.get('id')) is not int or person['id']<=0:
            raise signing.BadSignature('Invalid participant')
        if not isinstance(person.get('name'),str) or not person['name'] or len(person['name'])>150:
            raise signing.BadSignature('Invalid participant name')
    if claims['setter']['id']==claims['advisor']['id']:raise signing.BadSignature('Distinct roles required')
    return claims
