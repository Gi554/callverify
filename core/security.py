import base64
import hashlib
import hmac
import secrets
from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

def cipher():
    key = settings.MFA_ENCRYPTION_KEY
    if not key:
        if not settings.DEBUG:
            raise ImproperlyConfigured('MFA_ENCRYPTION_KEY required')
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(key)

def encrypt_secret(value):
    return 'enc:' + cipher().encrypt(value.encode()).decode()

def decrypt_secret(value):
    if value.startswith('enc:'):
        return cipher().decrypt(value[4:].encode()).decode()
    return value  # Legacy rows are upgraded by encrypt_mfa before deployment.

def recovery_hash(value):
    return hmac.new(settings.SECRET_KEY.encode(), value.replace('-','').upper().encode(),hashlib.sha256).hexdigest()

def generate_backup_codes(user):
    codes = ['-'.join([token[i:i+4] for i in range(0,16,4)]) for token in [secrets.token_hex(8).upper() for _ in range(10)]]
    user.backup_codes = [recovery_hash(code) for code in codes]
    user.save(update_fields=['backup_codes'])
    return codes

def consume_backup(user, value):
    if not isinstance(value,str) or len(value.replace('-','')) != 16:
        return False
    digest = recovery_hash(value)
    for stored in user.backup_codes:
        if hmac.compare_digest(stored,digest):
            user.backup_codes.remove(stored)
            user.save(update_fields=['backup_codes'])
            return True
    return False
