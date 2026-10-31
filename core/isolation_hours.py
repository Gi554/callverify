"""Single Isolation client's weekly working hours in Québec."""

from datetime import datetime, time, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo
from django.db import transaction
from django.db.models import F
from rest_framework import serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import IsolationWorkingHours, IsolationVisitCalendar, AuditEvent
from .isolation_work import VisitAuthentication, Conflict

ZONE = ZoneInfo('America/Toronto')
UTC = dt_timezone.utc


class Window(serializers.Serializer):
    weekday = serializers.IntegerField(min_value=0, max_value=6)
    start = serializers.RegexField(r'^([01][0-9]|2[0-3]):[0-5][0-9]$')
    end = serializers.RegexField(r'^([01][0-9]|2[0-3]):[0-5][0-9]$')

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError('Champs de plage non autorisés.')
        return super().to_internal_value(data)

    def validate(self, data):
        if data['end'] <= data['start']:
            raise serializers.ValidationError('Début avant fin, le même jour.')
        return data


class Input(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0)
    enabled = serializers.BooleanField()
    windows = Window(many=True, max_length=28)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise serializers.ValidationError('Champs non autorisés.')
        rows = sorted(data['windows'], key=lambda row: (row['weekday'], row['start']))
        for a, b in zip(rows, rows[1:]):
            if a['weekday'] == b['weekday'] and a['end'] > b['start']:
                raise serializers.ValidationError('Plages horaires en chevauchement.')
        data['windows'] = rows
        return data


def rules():
    row = IsolationWorkingHours.objects.filter(pk=1).first()
    return {
        'enabled': row.enabled if row else False,
        'windows': row.windows if row else [],
        'revision': row.revision if row else 0,
    }


@api_view(['GET', 'POST'])
@authentication_classes([VisitAuthentication])
@permission_classes([IsAuthenticated])
def configuration(request):
    if request.user.role not in ('client', 'administrator'):
        raise PermissionDenied('Horaires réservés au client et à l’administration Isolation.')
    if request.method == 'POST':
        serializer = Input(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            # Same global lock order as reservations: client calendar(s), then hours.
            for pk in IsolationVisitCalendar.objects.order_by('pk').values_list('pk', flat=True):
                IsolationVisitCalendar.objects.filter(pk=pk).update(version=F('version') + 1)
            IsolationWorkingHours.objects.get_or_create(pk=1)
            before = rules()
            if not IsolationWorkingHours.objects.filter(pk=1, revision=data['revision']).update(
                enabled=data['enabled'], windows=data['windows'], revision=F('revision') + 1
            ):
                raise Conflict('Horaires modifiés : rechargez.')
            AuditEvent.objects.create(
                action='isolation.working_hours.updated',
                object_id='1',
                metadata={'actor_portal_id': request.user.pk, 'before': before, 'after': rules()},
            )
    response = Response({**rules(), 'timezone': 'America/Toronto'})
    response['Cache-Control'] = 'no-store'
    return response


def ensure_open(start, end):
    # Serialize with policy writes, including the first booking before any hours exist.
    IsolationWorkingHours.objects.get_or_create(pk=1)
    IsolationWorkingHours.objects.filter(pk=1).update(revision=F('revision'))
    policy = rules()
    if not policy['enabled']:
        return  # legacy unrestricted mode, explicitly shown in settings
    first, last = start.astimezone(ZONE), end.astimezone(ZONE)
    if first.date() == last.date() and any(
        w['weekday'] == first.weekday()
        and time.fromisoformat(w['start']) <= first.time()
        and last.time() <= time.fromisoformat(w['end'])
        for w in policy['windows']
    ):
        return
    raise Conflict('Ce créneau est en dehors des horaires du client Isolation.')


def closed_periods(start, end):
    policy = rules()
    if not policy['enabled']:
        return []
    start, end = start.astimezone(UTC), end.astimezone(UTC)
    day, last = start.astimezone(ZONE).date(), end.astimezone(ZONE).date()
    intervals = []
    while day <= last:
        for row in policy['windows']:
            if row['weekday'] != day.weekday():
                continue
            local = [
                datetime.combine(day, time.fromisoformat(row[key])) for key in ('start', 'end')
            ]
            bounds = [value.replace(tzinfo=ZONE).astimezone(UTC) for value in local]
            if any(
                value.astimezone(ZONE).replace(tzinfo=None) != wall
                for value, wall in zip(bounds, local)
            ):
                continue
            a, b = max(start, bounds[0]), min(end, bounds[1])
            if a < b:
                intervals.append((a, b))
        day += timedelta(days=1)
    cursor, result = start, []
    for a, b in sorted(intervals):
        if a > cursor:
            result.append({'starts_at': cursor, 'ends_at': a, 'reason': 'working_hours'})
        cursor = max(cursor, b)
    if cursor < end:
        result.append({'starts_at': cursor, 'ends_at': end, 'reason': 'working_hours'})
    return result
