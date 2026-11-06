"""Central portal TOTP MFA. Secrets are encrypted; backup codes are hashed and single-use."""

import base64
import hashlib
import hmac
import io
import secrets
import struct
import time
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from core.security import recovery_hash
from .models import AccessAudit, Membership, PortalMFA


class MFAActionThrottle(UserRateThrottle):
    scope = 'portal_mfa'


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
    if not value.startswith('enc:'):
        raise InvalidToken
    return cipher().decrypt(value[4:].encode()).decode()


def totp_step(secret, code, *, now=None):
    if not isinstance(code, str) or len(code) != 6 or not code.isdigit():
        return None
    try:
        key = base64.b32decode(secret, casefold=False)
    except (ValueError, TypeError):
        return None
    counter = int((time.time() if now is None else now) // 30)
    for step in (counter - 1, counter, counter + 1):
        digest = hmac.new(key, struct.pack('>Q', step), hashlib.sha1).digest()
        offset = digest[-1] & 15
        number = (struct.unpack('>I', digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
        if hmac.compare_digest(f'{number:06d}', code):
            return step
    return None


def admin_requires_mfa(user):
    return Membership.objects.filter(user=user, active=True, role='administrator').exists()


def mfa_enabled(user):
    return PortalMFA.objects.filter(user=user, enabled_at__isnull=False).exists()


def backup_codes_remaining(user):
    row = PortalMFA.objects.filter(user=user, enabled_at__isnull=False).only('backup_codes').first()
    return len(row.backup_codes) if row else 0


def new_backup_codes():
    codes = []
    for _ in range(10):
        token = secrets.token_hex(8).upper()
        codes.append('-'.join(token[i : i + 4] for i in range(0, 16, 4)))
    return codes, [recovery_hash(code) for code in codes]


def authenticate_code(row, code):
    try:
        step = totp_step(decrypt_secret(row.secret), code)
    except (InvalidToken, ImproperlyConfigured, ValueError):
        step = None
    if step is not None and step > row.last_step:
        row.last_step = step
        row.save(update_fields=['last_step'])
        return True

    digest = recovery_hash(code) if isinstance(code, str) else ''
    for stored in row.backup_codes:
        if hmac.compare_digest(stored, digest):
            row.backup_codes.remove(stored)
            row.save(update_fields=['backup_codes'])
            return True
    return False


class MFAInput(serializers.Serializer):
    action = serializers.ChoiceField(choices=('enroll', 'confirm', 'backup'))
    code = serializers.CharField(required=False, allow_blank=True, max_length=40)
    password = serializers.CharField(
        required=False, allow_blank=True, max_length=256, write_only=True
    )

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs MFA non autorisés')
        return data


@api_view(['POST'])
@throttle_classes([MFAActionThrottle])
def manage_mfa(request):
    serializer = MFAInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    action = serializer.validated_data['action']
    data = serializer.validated_data
    current = PortalMFA.objects.filter(user=request.user, enabled_at__isnull=False).first()

    if action == 'enroll':
        if current:
            raise ValidationError('La MFA est déjà activée.')
        secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')
        request.session['portal_pending_mfa'] = encrypt_secret(secret)
        request.session.modified = True
        from qrcode.image.svg import SvgPathImage
        import qrcode

        uri = (
            f'otpauth://totp/{quote("Orvia CRM:" + request.user.username)}'
            f'?secret={secret}&issuer=Orvia%20CRM&digits=6&period=30'
        )
        output = io.BytesIO()
        qrcode.make(uri, image_factory=SvgPathImage).save(output)
        import base64 as base64_module

        AccessAudit.objects.create(user=request.user, action='mfa.enrollment_started')
        response = Response(
            {
                'uri': uri,
                'qr': 'data:image/svg+xml;base64,'
                + base64_module.b64encode(output.getvalue()).decode(),
            }
        )
        response['Cache-Control'] = 'no-store'
        return response

    if action == 'confirm':
        pending = request.session.get('portal_pending_mfa', '')
        try:
            secret = decrypt_secret(pending)
        except (InvalidToken, ImproperlyConfigured, ValueError):
            raise ValidationError('Recommencez la configuration MFA.') from None
        step = totp_step(secret, data.get('code', ''))
        if step is None:
            raise ValidationError({'code': 'Code invalide ou expiré.'})
        codes, hashes = new_backup_codes()
        with transaction.atomic():
            row = PortalMFA.objects.select_for_update().filter(user=request.user).first()
            if row and row.enabled_at:
                raise ValidationError('La MFA est déjà activée.')
            if row:
                row.secret = encrypt_secret(secret)
                row.enabled_at = timezone.now()
                row.last_step = step
                row.backup_codes = hashes
                row.save(update_fields=['secret', 'enabled_at', 'last_step', 'backup_codes'])
            else:
                PortalMFA.objects.create(
                    user=request.user,
                    secret=encrypt_secret(secret),
                    enabled_at=timezone.now(),
                    last_step=step,
                    backup_codes=hashes,
                )
            AccessAudit.objects.create(user=request.user, action='mfa.enabled')
        request.session.pop('portal_pending_mfa', None)
        request.session.pop('portal_mfa_setup_required', None)
        request.session.modified = True
        response = Response({'enabled': True, 'backup_codes': codes})
        response['Cache-Control'] = 'no-store'
        return response

    if not current:
        raise ValidationError('Activez d’abord la MFA.')
    with transaction.atomic():
        row = PortalMFA.objects.select_for_update().get(user=request.user, enabled_at__isnull=False)
        try:
            step = totp_step(decrypt_secret(row.secret), data.get('code', ''))
        except (InvalidToken, ImproperlyConfigured, ValueError):
            raise ValidationError('Configuration MFA indisponible.') from None
        if (
            not request.user.check_password(data.get('password', ''))
            or step is None
            or step <= row.last_step
        ):
            raise ValidationError('Mot de passe et nouveau code MFA requis.')
        row.last_step = step
        codes, row.backup_codes = new_backup_codes()
        row.save(update_fields=['last_step', 'backup_codes'])
        AccessAudit.objects.create(user=request.user, action='mfa.backup_regenerated')
    response = Response({'backup_codes': codes})
    response['Cache-Control'] = 'no-store'
    return response
