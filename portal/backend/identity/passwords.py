"""Authenticated password rotation, with no credential material in the audit."""
from django.contrib.auth import get_user_model,update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import F
from rest_framework import serializers
from rest_framework.decorators import api_view,throttle_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from .models import AccessAudit

class PasswordThrottle(UserRateThrottle):
    scope='portal_password'

class PasswordInput(serializers.Serializer):
    current_password=serializers.CharField(max_length=256,trim_whitespace=False,write_only=True)
    new_password=serializers.CharField(max_length=256,trim_whitespace=False,write_only=True)
    confirmation=serializers.CharField(max_length=256,trim_whitespace=False,write_only=True)
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise ValidationError('Champs non autorisés')
        if data['new_password']!=data['confirmation']:raise ValidationError('La confirmation ne correspond pas')
        return data

@api_view(['POST'])
@throttle_classes([PasswordThrottle])
def change_password(request):
    serializer=PasswordInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
    with transaction.atomic():
        # Conditional ownership remains session-authenticated; the write obtains
        # a row lock on PostgreSQL before checking the latest password hash.
        users=get_user_model().objects.filter(pk=request.user.pk,is_active=True)
        if not users.update(password=F('password')):raise ValidationError('Compte indisponible')
        user=users.get()
        if not user.check_password(data['current_password']):raise ValidationError('Mot de passe actuel incorrect')
        if user.check_password(data['new_password']):raise ValidationError('Choisissez un mot de passe différent du précédent')
        try:validate_password(data['new_password'],user=user)
        except DjangoValidationError as error:raise ValidationError({'new_password':error.messages})
        user.set_password(data['new_password']);user.save(update_fields=['password'])
        AccessAudit.objects.create(user=user,action='account.password_changed',metadata={})
    # Rotate this session and preserve its authentication. Other sessions retain
    # the old hash and are rejected on their next authenticated request.
    update_session_auth_hash(request,user)
    response=Response(status=204);response['Cache-Control']='no-store'
    return response
