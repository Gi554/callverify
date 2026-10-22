"""Revoke other central sessions without storing device or session identifiers in audits."""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from rest_framework import serializers
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from .models import SessionGeneration, AccessAudit
from .passwords import PasswordThrottle
from .authentication import SESSION_KEY


class RevokeInput(serializers.Serializer):
    current_password = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés')
        return data


@api_view(['POST'])
@throttle_classes([PasswordThrottle])
def revoke_others(request):
    serializer = RevokeInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    expected = request.session.get(SESSION_KEY, 0)
    with transaction.atomic():
        users = get_user_model().objects.filter(pk=request.user.pk, is_active=True)
        if not users.update(password=F('password')):
            raise PermissionDenied('Compte indisponible')
        user = users.get()
        if not user.check_password(data['current_password']):
            raise ValidationError('Mot de passe actuel incorrect')
        SessionGeneration.objects.get_or_create(user=user)
        if not SessionGeneration.objects.filter(user=user, generation=expected).update(
            generation=F('generation') + 1
        ):
            raise PermissionDenied('Session révoquée : reconnectez-vous')
        AccessAudit.objects.create(user=user, action='account.other_sessions_revoked', metadata={})
    # A lost response may also lose the renewed session: reconnect rather than restore a revoked session.
    request.session.cycle_key()
    request.session[SESSION_KEY] = expected + 1
    response = Response(status=204)
    response['Cache-Control'] = 'no-store'
    return response
