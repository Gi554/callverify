"""Server-side call guard rails: permitted calling hours and a do-not-call list."""

import re
from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from .management_api import require_admin
from .models import AccessAudit, CallExclusion, CallRules

MAX_BATCH = 1000


def rules():
    row, _ = CallRules.objects.get_or_create(pk=1)
    return row


def normalize(raw):
    """North-American number as the 11 digits that are dialed (1NXXNXXXXXX), or None."""
    if not isinstance(raw, str) or not re.fullmatch(r'\+?[0-9 ().-]+', raw.strip()):
        return None
    digits = re.sub(r'[ ().-]', '', raw.strip()).removeprefix('+')
    if len(digits) == 10:
        digits = '1' + digits
    return digits if re.fullmatch(r'1[2-9][0-9]{2}[2-9][0-9]{6}', digits) else None


def clock(value):
    return value if isinstance(value, time) else time.fromisoformat(str(value))


def current_time():
    return timezone.now()


def window(row, now=None):
    """(allowed, message) for the current moment, in the configured time zone."""
    if not row.enforce_hours:
        return True, ''
    local = (now or current_time()).astimezone(ZoneInfo(row.timezone))
    weekend = local.weekday() >= 5
    start = clock(row.weekend_start if weekend else row.weekday_start)
    end = clock(row.weekend_end if weekend else row.weekday_end)
    if start <= local.time().replace(tzinfo=None) < end:
        return True, ''
    return False, (
        f'Appels autorisés de {start:%H:%M} à {end:%H:%M} '
        f'({"week-end" if weekend else "semaine"}, heure de {row.timezone.split("/")[-1]}). '
        'Réessayez pendant ces heures.'
    )


def refusal(destination, now=None):
    """Reason why this call must not be placed, or an empty string."""
    allowed, message = window(rules(), now)
    if not allowed:
        return message
    if CallExclusion.objects.filter(number=destination).exists():
        return 'Ce numéro est sur la liste d’exclusion : appel refusé.'
    return ''


class RulesInput(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0)
    enforce_hours = serializers.BooleanField()
    timezone = serializers.CharField(max_length=60)
    weekday_start = serializers.TimeField()
    weekday_end = serializers.TimeField()
    weekend_start = serializers.TimeField()
    weekend_end = serializers.TimeField()

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés')
        try:
            ZoneInfo(data['timezone'])
        except (ZoneInfoNotFoundError, ValueError):
            raise ValidationError({'timezone': 'Fuseau horaire inconnu'})
        for kind in ('weekday', 'weekend'):
            if data[kind + '_start'] >= data[kind + '_end']:
                raise ValidationError('L’heure de début doit précéder l’heure de fin.')
        return data


class ExclusionInput(serializers.Serializer):
    numbers = serializers.CharField(max_length=60000)
    reason = serializers.CharField(max_length=200, allow_blank=True, required=False, default='')

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés')
        return data


def rules_output(row):
    allowed, message = window(row)
    return {
        'enforce_hours': row.enforce_hours,
        'timezone': row.timezone,
        'weekday_start': f'{clock(row.weekday_start):%H:%M}',
        'weekday_end': f'{clock(row.weekday_end):%H:%M}',
        'weekend_start': f'{clock(row.weekend_start):%H:%M}',
        'weekend_end': f'{clock(row.weekend_end):%H:%M}',
        'revision': row.revision,
        'allowed_now': allowed,
        'message': message,
    }


@api_view(['GET', 'PATCH'])
def settings_view(request, workspace):
    require_admin(request.user, workspace)
    if request.method == 'GET':
        response = Response(rules_output(rules()))
        response['Cache-Control'] = 'no-store'
        return response
    serializer = RulesInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    revision = data.pop('revision')
    rules()
    with transaction.atomic():
        if not CallRules.objects.filter(pk=1, revision=revision).update(
            **data, revision=F('revision') + 1, updated_at=timezone.now()
        ):
            raise ValidationError('Règles modifiées ailleurs : actualisez la page.')
        AccessAudit.objects.create(
            user=request.user,
            workspace=workspace,
            action='call_rules.updated',
            metadata={key: str(value) for key, value in data.items()},
        )
    return Response(rules_output(CallRules.objects.get(pk=1)))


def exclusion_output(row):
    return {'id': row.pk, 'number': row.number, 'reason': row.reason, 'created_at': row.created_at}


@api_view(['GET', 'POST'])
def exclusions(request, workspace):
    require_admin(request.user, workspace)
    if request.method == 'GET':
        qs = CallExclusion.objects.order_by('-pk')
        term = re.sub(r'\D', '', request.query_params.get('search', ''))
        if term:
            qs = qs.filter(number__contains=term)
        pager = PageNumberPagination()
        pager.page_size = 25
        rows = pager.paginate_queryset(qs, request)
        return pager.get_paginated_response([exclusion_output(row) for row in rows])
    serializer = ExclusionInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    parts = [part for part in re.split(r'[\n\r,;]+', data['numbers']) if part.strip()]
    if not parts:
        raise ValidationError('Aucun numéro fourni.')
    if len(parts) > MAX_BATCH:
        raise ValidationError(f'{MAX_BATCH} numéros au maximum à la fois.')
    valid, invalid = [], []
    for part in parts:
        number = normalize(part)
        (valid if number else invalid).append(number or part.strip()[:40])
    unique = list(dict.fromkeys(valid))
    with transaction.atomic():
        known = set(
            CallExclusion.objects.filter(number__in=unique).values_list('number', flat=True)
        )
        fresh = [number for number in unique if number not in known]
        CallExclusion.objects.bulk_create(
            [
                CallExclusion(number=number, reason=data['reason'], created_by=request.user)
                for number in fresh
            ]
        )
        AccessAudit.objects.create(
            user=request.user,
            workspace=workspace,
            action='call_exclusion.added',
            metadata={'added': len(fresh), 'already_listed': len(known), 'invalid': len(invalid)},
        )
    return Response(
        {'added': len(fresh), 'already_listed': len(known), 'invalid': invalid[:20]}, status=201
    )


@api_view(['DELETE'])
def exclusion_detail(request, workspace, pk):
    require_admin(request.user, workspace)
    with transaction.atomic():
        deleted, _ = CallExclusion.objects.filter(pk=pk).delete()
        if not deleted:
            raise ValidationError('Numéro introuvable.')
        AccessAudit.objects.create(
            user=request.user,
            workspace=workspace,
            action='call_exclusion.removed',
            metadata={'id': pk},
        )
    return Response(status=204)
