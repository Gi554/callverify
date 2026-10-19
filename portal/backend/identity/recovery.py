"""Central password recovery. No account discovery or tokens in API responses."""
from urllib.parse import urlsplit
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode,urlsafe_base64_decode
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view,authentication_classes,permission_classes,throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from .models import AccessAudit

class RecoveryThrottle(AnonRateThrottle):scope='portal_recovery'
class ResetThrottle(AnonRateThrottle):scope='portal_reset'

def public_url():
    value=settings.PORTAL_PUBLIC_URL.rstrip('/')
    parsed=urlsplit(value)
    if parsed.scheme not in ('http','https') or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Configure PORTAL_PUBLIC_URL')
    if not settings.DEBUG and parsed.scheme!='https':raise ValueError('HTTPS required')
    return value

def reply():
    response=Response({'detail':'Si un compte actif correspond à cette adresse, un lien de récupération sera envoyé.'})
    response['Cache-Control']='no-store'
    return response

class EmailInput(serializers.Serializer):
    email=serializers.EmailField(max_length=254)
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise ValidationError('Champs non autorisés')
        return data

class ResetInput(serializers.Serializer):
    uid=serializers.CharField(max_length=100)
    token=serializers.CharField(max_length=150)
    password=serializers.CharField(max_length=256,trim_whitespace=False,write_only=True)
    confirmation=serializers.CharField(max_length=256,trim_whitespace=False,write_only=True)
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise ValidationError('Champs non autorisés')
        if data['password']!=data['confirmation']:raise ValidationError('La confirmation ne correspond pas')
        return data

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([RecoveryThrottle])
def request_reset(request):
    SessionAuthentication().enforce_csrf(request)
    serializer=EmailInput(data=request.data);serializer.is_valid(raise_exception=True)
    # Ambiguous addresses cannot be used to select an arbitrary account.
    users=list(get_user_model().objects.filter(email__iexact=serializer.validated_data['email'],is_active=True)[:2])
    if len(users)!=1 or not users[0].has_usable_password():return reply()
    user=users[0]
    try:
        uid=urlsafe_base64_encode(force_bytes(user.pk));token=default_token_generator.make_token(user)
        link=f'{public_url()}/crm#reset={uid}:{token}'
        sent=send_mail('AMX — Réinitialiser votre mot de passe',
            f'Une récupération du mot de passe AMX a été demandée.\n\n{link}\n\nCe lien expire dans 30 minutes et ne peut être utilisé qu’une fois. Si vous n’êtes pas à l’origine de cette demande, ignorez cet e-mail.',
            settings.DEFAULT_FROM_EMAIL,[user.email],fail_silently=False)
    except Exception:
        # Never log the exception: SMTP failures can contain recipient/token data.
        AccessAudit.objects.create(user=user,action='account.recovery_mail_failed',metadata={})
    else:
        AccessAudit.objects.create(user=user,action='account.recovery_requested' if sent else 'account.recovery_mail_failed',metadata={})
    return reply()

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([ResetThrottle])
def confirm_reset(request):
    SessionAuthentication().enforce_csrf(request)
    serializer=ResetInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
    try:pk=int(urlsafe_base64_decode(data['uid']).decode())
    except (ValueError,TypeError,UnicodeDecodeError,OverflowError):raise ValidationError('Lien invalide ou expiré')
    if pk<=0 or pk>9223372036854775807:raise ValidationError('Lien invalide ou expiré')
    with transaction.atomic():
        users=get_user_model().objects.filter(pk=pk,is_active=True)
        if not users.update(password=F('password')):raise ValidationError('Lien invalide ou expiré')
        user=users.get()
        if not user.has_usable_password() or not default_token_generator.check_token(user,data['token']):raise ValidationError('Lien invalide ou expiré')
        if user.check_password(data['password']):raise ValidationError('Choisissez un nouveau mot de passe différent')
        try:validate_password(data['password'],user=user)
        except DjangoValidationError as error:raise ValidationError({'password':error.messages})
        user.set_password(data['password']);user.save(update_fields=['password'])
        AccessAudit.objects.create(user=user,action='account.password_reset',metadata={})
    response=Response(status=204);response['Cache-Control']='no-store'
    return response
