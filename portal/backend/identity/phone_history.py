"""Manual, scoped 511 outgoing history; never persists global provider records."""

import json
from urllib.parse import urlsplit
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from django.conf import settings
from django.core import signing
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.exceptions import APIException, ValidationError, PermissionDenied
from rest_framework.response import Response
from packages.access.phone_history import verify, number
from packages.access.tickets import issue
from packages.newt.cdr import fetch_records
from packages.newt.directory import DirectoryUnavailable
from .models import Membership, PhoneExtension, PhoneDirectoryGate, AccessAudit
from .phone_directory import DirectoryThrottle


class Input(serializers.Serializer):
    proof = serializers.CharField(max_length=8192, write_only=True)
    starts_on = serializers.DateField(input_formats=['%Y-%m-%d'])
    ends_on = serializers.DateField(input_formats=['%Y-%m-%d'])
    page = serializers.IntegerField(min_value=1, default=1)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés.')
        today = timezone.now().astimezone(ZoneInfo('America/Toronto')).date()
        if not 0 <= (data['ends_on'] - data['starts_on']).days <= 6 or data['ends_on'] > today:
            raise ValidationError('Sept dates maximum, sans date future, en heure de Montréal.')
        return data


class Unavailable(APIException):
    status_code = 503
    default_detail = 'Historique Phonetico indisponible ou format non reconnu. Aucun appel lancé.'


def authorized(user, workspace):
    if (
        not user.is_active
        or not Membership.objects.filter(
            user=user, workspace=workspace, role='setter', active=True
        ).exists()
    ):
        raise PermissionDenied('Setter actif requis dans cet espace.')


def eligible(user, workspace, claims, proof):
    base = (
        settings.ASSURANCE_INTERNAL_URL
        if workspace == 'assurance'
        else settings.ISOLATION_INTERNAL_URL
    ).rstrip('/')
    parsed = urlsplit(base)
    if (
        parsed.scheme not in ('http', 'https')
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        return False
    path = (
        f'/api/assurance/contacts/{claims["resource"]}/phone-history-check/'
        if workspace == 'assurance'
        else f'/api/work-queue/{claims["resource"]}/phone-history-check/'
    )
    try:
        with requests.post(
            base + path,
            json={'proof': proof},
            headers={'Authorization': 'Bearer ' + issue(user.pk, workspace, 'setter')},
            timeout=(5, 5),
            allow_redirects=False,
            stream=True,
        ) as response:
            if response.status_code != 200:
                return False
            raw = response.raw.read(1025, decode_content=True)
            return len(raw) <= 1024 and json.loads(raw) == {'eligible': True}
    except (requests.RequestException, ValueError, UnicodeError):
        return False


def scoped(rows, extension, destination, assigned_at, start, end):
    matched = []
    for row in rows:
        # Only confirmed outgoing interpretation: From exact extension and To full NANP number.
        if row['from'] != extension:
            continue
        try:
            if number(row['to']) != destination:
                continue
            instant = datetime.fromisoformat(row['occurred_at']) if row['occurred_at'] else None
            day = datetime.strptime(row['local_date'], '%Y-%m-%d').date()
        except (ValueError, TypeError):
            continue
        if (
            instant is None
            or timezone.is_naive(instant)
            or instant < assigned_at
            or not start <= day <= end
        ):
            continue
        matched.append(
            {
                key: row[key]
                for key in ('local_date', 'local_time', 'timezone', 'occurred_at', 'duration_raw')
            }
        )
    return sorted(matched, key=lambda row: row['occurred_at'], reverse=True)


@api_view(['POST'])
@throttle_classes([DirectoryThrottle])
def history(request, workspace):
    if workspace not in ('assurance', 'isolation'):
        raise ValidationError('Espace invalide.')
    authorized(request.user, workspace)
    if request.query_params:
        raise ValidationError('Aucun paramètre d’URL attendu.')
    serializer = Input(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    try:
        claims = verify(data['proof'], request.user.pk, workspace)
    except (signing.BadSignature, ValueError, TypeError, AttributeError):
        raise ValidationError('Preuve de fiche invalide ou expirée.') from None
    if (
        not settings.NEWT_CDR_HISTORY_ENABLED
        or not settings.NEWT_USERNAME
        or not settings.NEWT_PASSWORD
    ):
        raise Unavailable()
    try:
        with transaction.atomic():
            PhoneDirectoryGate.objects.get_or_create(pk=1)
            PhoneDirectoryGate.objects.filter(pk=1).update(revision=F('revision'))
            authorized(request.user, workspace)
            from django.contrib.auth import get_user_model

            get_user_model().objects.filter(pk=request.user.pk).update(password=F('password'))
            link = PhoneExtension.objects.filter(user=request.user, extension__isnull=False).first()
            if not link:
                raise ValidationError('Aucun poste associé à votre compte.')
            if not eligible(request.user, workspace, claims, data['proof']):
                raise PermissionDenied('Fiche modifiée ou accès retiré : actualisez.')
            rows = fetch_records(
                settings.NEWT_USERNAME, settings.NEWT_PASSWORD, data['starts_on'], data['ends_on']
            )
            authorized(request.user, workspace)
            if not eligible(request.user, workspace, claims, data['proof']):
                raise PermissionDenied('Fiche modifiée ou accès retiré pendant la consultation.')
            rows = scoped(
                rows,
                link.extension,
                claims['destination'],
                link.updated_at,
                data['starts_on'],
                data['ends_on'],
            )
            total = len(rows)
            offset = (data['page'] - 1) * 25
            AccessAudit.objects.create(
                user=request.user,
                workspace=workspace,
                action='phone.history_read',
                metadata={
                    'resource_id': claims['resource'],
                    'starts_on': str(data['starts_on']),
                    'ends_on': str(data['ends_on']),
                    'matched': total,
                    'page': data['page'],
                },
            )
    except DirectoryUnavailable:
        raise Unavailable() from None
    response = Response(
        {
            'results': rows[offset : offset + 25],
            'count': total,
            'page': data['page'],
            'has_next': offset + 25 < total,
            'timezone': 'America/Toronto',
            'source': 'NEWT 511',
            'checked_at': timezone.now(),
            'extension': link.extension,
            'assignment_since': link.updated_at,
            'starts_on': data['starts_on'],
            'ends_on': data['ends_on'],
            'definition': 'Appels sortants dont From correspond au poste actuellement associé et To au numéro actuel de la fiche. Uniquement depuis la dernière association du poste. Aucun rapprochement entrant ou appel sans date interprétable. Duration est brute, unité non confirmée. Ce journal ne prouve pas le décrochage humain ; une absence de ligne ne prouve pas une absence d’appel.',
        }
    )
    response['Cache-Control'] = 'no-store'
    return response
