import base64
import hashlib
import json
import secrets
from datetime import timedelta
from uuid import UUID
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.throttling import UserRateThrottle
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.response import Response
from packages.calendar_connectors import providers
from .models import CalendarConnection, CalendarAuthorization, Membership, AccessAudit, ROLES
from .recovery import public_url

OWNERS = {'assurance': 'advisor', 'isolation': 'client'}


class CalendarThrottle(UserRateThrottle):
    scope = 'portal_calendar'


class Unavailable(APIException):
    status_code = 503
    default_detail = 'Agenda indisponible : vérifiez la configuration ou reconnectez le compte. Aucun créneau libre ne peut être déduit de cet échec.'


def cipher():
    key = settings.PORTAL_CALENDAR_KEY
    if not key:
        if not settings.DEBUG:
            raise Unavailable()
        key = base64.urlsafe_b64encode(
            hashlib.sha256(('calendar:' + settings.SECRET_KEY).encode()).digest()
        )
    try:
        return Fernet(key)
    except (ValueError, TypeError):
        raise Unavailable() from None


def seal(value):
    return cipher().encrypt(json.dumps(value).encode()).decode()


def unseal(value):
    try:
        return json.loads(cipher().decrypt(value.encode()))
    except (InvalidToken, ValueError, TypeError, AttributeError):
        raise Unavailable() from None


def config(provider):
    if provider not in ('google', 'microsoft'):
        raise ValidationError('Fournisseur non autorisé')
    prefix = 'GOOGLE_CALENDAR' if provider == 'google' else 'MICROSOFT_CALENDAR'
    client = getattr(settings, prefix + '_CLIENT_ID')
    secret = getattr(settings, prefix + '_CLIENT_SECRET')
    tenant = settings.MICROSOFT_CALENDAR_TENANT
    if provider == 'microsoft' and tenant not in ('common', 'organizations', 'consumers'):
        try:
            tenant = str(UUID(tenant))
        except (ValueError, TypeError, AttributeError):
            raise Unavailable() from None
    if not client or not secret:
        raise Unavailable()
    try:
        redirect = public_url() + '/crm/oauth/' + provider
    except ValueError:
        raise Unavailable() from None
    cipher()
    return {'client_id': client, 'client_secret': secret, 'tenant': tenant, 'redirect': redirect}


def require_owner(user, workspace):
    if (
        workspace not in OWNERS
        or not Membership.objects.filter(
            user=user,
            user__is_active=True,
            workspace=workspace,
            role=OWNERS[workspace],
            active=True,
        ).exists()
    ):
        raise PermissionDenied(
            'Connexion réservée au propriétaire de son agenda : conseiller Assurance ou client Isolation'
        )


def session_hash(request):
    if not request.session.session_key:
        raise PermissionDenied('Session centrale requise')
    return hashlib.sha256(request.session.session_key.encode()).hexdigest()


class StrictInput(serializers.Serializer):
    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés')
        return data


class StartInput(StrictInput):
    provider = serializers.ChoiceField(choices=['google', 'microsoft'])


class RevisionInput(StrictInput):
    revision = serializers.IntegerField(min_value=0)


class CallbackInput(StrictInput):
    state = serializers.CharField(max_length=200)
    code = serializers.CharField(max_length=4096, required=False, trim_whitespace=False)
    error = serializers.CharField(max_length=200, required=False)

    def validate(self, data):
        super().validate(data)
        if ('code' in data) == ('error' in data):
            raise ValidationError('Réponse OAuth invalide')
        return data


class WindowInput(StrictInput):
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()

    def validate(self, data):
        super().validate(data)
        for key in ('starts_at', 'ends_at'):
            raw = parse_datetime(str(self.initial_data[key]))
            if raw is None or timezone.is_naive(raw):
                raise ValidationError('Décalage ISO 8601 explicite requis')
        if not timedelta(0) < data['ends_at'] - data['starts_at'] <= timedelta(days=31):
            raise ValidationError('Fenêtre positive limitée à 31 jours')
        return data


def validated(schema, data):
    value = schema(data=data)
    value.is_valid(raise_exception=True)
    return value.validated_data


@api_view(['GET'])
@throttle_classes([CalendarThrottle])
def connections(request):
    rows = []
    for workspace, role in OWNERS.items():
        if not Membership.objects.filter(
            user=request.user, workspace=workspace, role=role, active=True
        ).exists():
            continue
        row = CalendarConnection.objects.filter(user=request.user, workspace=workspace).first()
        ready = {}
        for provider in ('google', 'microsoft'):
            try:
                config(provider)
                ready[provider] = True
            except Unavailable:
                ready[provider] = False
        rows.append(
            {
                'workspace': workspace,
                'provider': row.provider if row else '',
                'connected': bool(row and row.connected),
                'revision': row.revision if row else 0,
                'auto_sync': bool(row and row.auto_sync),
                'configured': ready,
            }
        )
    response = Response({'connections': rows})
    response['Cache-Control'] = 'no-store'
    return response


@api_view(['POST'])
@throttle_classes([CalendarThrottle])
def start(request, workspace):
    require_owner(request.user, workspace)
    data = validated(StartInput, request.data)
    provider = data['provider']
    options = config(provider)
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    with transaction.atomic():
        row, _ = CalendarConnection.objects.get_or_create(user=request.user, workspace=workspace)
        CalendarConnection.objects.filter(pk=row.pk).update(revision=F('revision'))
        row.refresh_from_db()
        if row.events.exclude(status__in=['removed', 'abandoned']).exists():
            raise ValidationError(
                'Retirez les événements Orvia ou confirmez leur nettoyage manuel avant de remplacer cet agenda'
            )
        CalendarAuthorization.objects.create(
            user=request.user,
            workspace=workspace,
            provider=provider,
            state_hash=hashlib.sha256(state.encode()).hexdigest(),
            session_hash=session_hash(request),
            verifier=seal(verifier),
            revision=row.revision,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        AccessAudit.objects.create(
            user=request.user,
            workspace=workspace,
            action='calendar.authorization_started',
            metadata={'provider': provider},
        )
    response = Response(
        {
            'authorization_url': providers.authorization(
                provider, options, options['redirect'], state, verifier
            )
        }
    )
    response['Cache-Control'] = 'no-store'
    return response


@api_view(['POST'])
@throttle_classes([CalendarThrottle])
def callback(request, provider):
    options = config(provider)
    data = validated(CallbackInput, request.data)
    attempt = CalendarAuthorization.objects.filter(
        user=request.user,
        provider=provider,
        state_hash=hashlib.sha256(data['state'].encode()).hexdigest(),
        session_hash=session_hash(request),
        used=False,
        expires_at__gt=timezone.now(),
    ).first()
    if not attempt:
        raise ValidationError('Autorisation expirée, déjà utilisée ou liée à une autre session')
    require_owner(request.user, attempt.workspace)
    if not CalendarAuthorization.objects.filter(
        pk=attempt.pk, used=False, expires_at__gt=timezone.now()
    ).update(used=True, verifier=''):
        raise ValidationError('Autorisation déjà utilisée')
    if 'error' in data:
        raise ValidationError('Autorisation refusée. Vous pouvez recommencer la connexion.')
    verifier = unseal(attempt.verifier)
    try:
        tokens, seconds = providers.tokens(
            provider, options, code=data['code'], redirect=options['redirect'], verifier=verifier
        )
    except providers.ProviderError:
        raise Unavailable() from None
    with transaction.atomic():
        require_owner(request.user, attempt.workspace)
        owner_connection = CalendarConnection.objects.get(
            user=request.user, workspace=attempt.workspace
        )
        CalendarConnection.objects.filter(pk=owner_connection.pk).update(revision=F('revision'))
        if owner_connection.events.exclude(status__in=['removed', 'abandoned']).exists():
            raise ValidationError('Retirez les événements Orvia avant de remplacer cet agenda')
        changed = CalendarConnection.objects.filter(
            user=request.user, workspace=attempt.workspace, revision=attempt.revision
        ).update(
            provider=provider,
            payload=seal(tokens),
            connected=True,
            auto_sync=False,
            expires_at=timezone.now() + timedelta(seconds=seconds),
            revision=F('revision') + 1,
        )
        if not changed:
            raise ValidationError('Connexion modifiée entre-temps : recommencez')
        AccessAudit.objects.create(
            user=request.user,
            workspace=attempt.workspace,
            action='calendar.connected',
            metadata={'provider': provider},
        )
    response = Response({'workspace': attempt.workspace, 'connected': True, 'provider': provider})
    response['Cache-Control'] = 'no-store'
    return response


@api_view(['POST'])
@throttle_classes([CalendarThrottle])
def disconnect(request, workspace):
    if workspace not in ROLES:
        raise ValidationError('Espace invalide')
    data = validated(RevisionInput, request.data)
    with transaction.atomic():
        row = CalendarConnection.objects.filter(user=request.user, workspace=workspace).first()
        if row:
            CalendarConnection.objects.filter(pk=row.pk).update(revision=F('revision'))
            if row.events.exclude(status__in=['removed', 'abandoned']).exists():
                raise ValidationError('Retirez les événements Orvia avant de déconnecter cet agenda')
        if not row or not CalendarConnection.objects.filter(
            pk=row.pk, revision=data['revision']
        ).update(
            payload='',
            connected=False,
            auto_sync=False,
            expires_at=None,
            revision=F('revision') + 1,
        ):
            raise ValidationError('Connexion modifiée : actualisez')
        CalendarAuthorization.objects.filter(
            user=request.user, workspace=workspace, used=False
        ).update(used=True, verifier='')
        AccessAudit.objects.create(
            user=request.user, workspace=workspace, action='calendar.disconnected', metadata={}
        )
    response = Response(status=204)
    response['Cache-Control'] = 'no-store'
    return response


def availability(user, workspace, data):
    require_owner(user, workspace)
    failure = False
    with transaction.atomic():
        row = CalendarConnection.objects.filter(
            user=user, workspace=workspace, connected=True
        ).first()
        if not row or not CalendarConnection.objects.filter(pk=row.pk, connected=True).update(
            revision=F('revision')
        ):
            raise Unavailable()
        row.refresh_from_db()
        options = config(row.provider)
        tokens = unseal(row.payload)
        try:
            if (
                not isinstance(tokens, dict)
                or not tokens.get('access')
                or not tokens.get('refresh')
            ):
                raise providers.ProviderError(True)
            if row.expires_at is None or row.expires_at <= timezone.now() + timedelta(seconds=60):
                tokens, seconds = providers.tokens(row.provider, options, refresh=tokens['refresh'])
                row.payload = seal(tokens)
                row.expires_at = timezone.now() + timedelta(seconds=seconds)
                row.save(update_fields=['payload', 'expires_at'])
            periods = providers.busy(
                row.provider, tokens['access'], data['starts_at'], data['ends_at']
            )
        except providers.ProviderError as error:
            failure = True
            if error.reauthorize:
                row.connected = False
                row.auto_sync = False
                row.payload = ''
                row.expires_at = None
                row.revision += 1
                row.save(
                    update_fields=['connected', 'auto_sync', 'payload', 'expires_at', 'revision']
                )
                AccessAudit.objects.create(
                    user=user,
                    workspace=workspace,
                    action='calendar.reauthorization_required',
                    metadata={'provider': row.provider},
                )
        require_owner(user, workspace)
    if failure:
        raise Unavailable()
    return periods


@api_view(['POST'])
@throttle_classes([CalendarThrottle])
def busy(request, workspace):
    data = validated(WindowInput, request.data)
    response = Response(
        {
            'busy': availability(request.user, workspace, data),
            'calendar': 'primary',
            'checked_at': timezone.now(),
        }
    )
    response['Cache-Control'] = 'no-store'
    return response
