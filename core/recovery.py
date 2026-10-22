from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.views.decorators.csrf import csrf_protect
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from .models import AdminUser
from .views import LoginThrottle, audit


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
@csrf_protect
def reset_request(request):
    email = request.data.get('email', '')
    if not isinstance(email, str):
        raise ValidationError('Email invalide')
    for user in AdminUser.objects.filter(
        email__iexact=email, is_staff=True, is_active=True
    ).exclude(email=''):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        url = f'{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}'
        send_mail(
            'Réinitialisation CallVerify',
            f'Lien valable une heure : {url}',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        )
        audit(user, 'password.reset_requested')
    return Response({'detail': 'Si un compte correspond, un lien de récupération sera envoyé.'})


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
@csrf_protect
def reset_confirm(request):
    try:
        user_id = force_str(urlsafe_base64_decode(request.data.get('uid', '')))
        with transaction.atomic():
            user = AdminUser.objects.select_for_update().get(
                pk=user_id, is_staff=True, is_active=True
            )
            if not default_token_generator.check_token(user, request.data.get('token', '')):
                raise ValidationError('Lien invalide ou expiré')
            password = request.data.get('password', '')
            validate_password(password, user=user)
            user.set_password(password)
            user.save(update_fields=['password'])
            audit(user, 'password.reset_completed')
    except (AdminUser.DoesNotExist, ValueError, TypeError, OverflowError):
        raise ValidationError('Lien invalide ou expiré')
    except DjangoValidationError as error:
        raise ValidationError(error.messages)
    return Response({'detail': 'Mot de passe mis à jour; les anciennes sessions sont invalidées.'})
