"""Personal weekly booking hours, serialized with appointment reservations."""

from datetime import datetime, time, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db import transaction
from django.db.models import F
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from .leases import Conflict
from .models import AdvisorSchedule, BusinessAudit

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
            raise serializers.ValidationError('Plage invalide : début avant fin, le même jour.')
        return data


class Input(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0)
    enabled = serializers.BooleanField()
    timezone = serializers.CharField(max_length=100)
    windows = Window(many=True, max_length=28)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise serializers.ValidationError('Champs non autorisés.')
        try:
            ZoneInfo(data['timezone'])
        except (ZoneInfoNotFoundError, ValueError):
            raise serializers.ValidationError('Fuseau horaire inconnu.') from None
        ordered = sorted(data['windows'], key=lambda row: (row['weekday'], row['start']))
        for previous, following in zip(ordered, ordered[1:]):
            if previous['weekday'] == following['weekday'] and previous['end'] > following['start']:
                raise serializers.ValidationError('Deux plages du même jour se chevauchent.')
        data['windows'] = ordered
        return data


def output(row):
    return {
        'revision': row.availability_revision if row else 0,
        'enabled': row.availability.get('enabled', False) if row else False,
        'timezone': row.availability.get('timezone', 'America/Toronto')
        if row
        else 'America/Toronto',
        'windows': row.availability.get('windows', []) if row else [],
    }


def configuration(advisor_id):
    return output(AdvisorSchedule.objects.filter(advisor_id=advisor_id).first())


@api_view(['GET', 'POST'])
def availability(request):
    if request.user.role != 'advisor':
        raise PermissionDenied('Disponibilités personnelles réservées au conseiller.')
    if request.method == 'POST':
        serializer = Input(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            row, _ = AdvisorSchedule.objects.get_or_create(advisor_id=request.user.pk)
            AdvisorSchedule.objects.filter(pk=row.pk).update(version=F('version'))
            row.refresh_from_db()
            if row.availability_revision != data['revision']:
                raise Conflict('Disponibilités modifiées : rechargez avant de réessayer.')
            before = output(row)
            new = {key: data[key] for key in ('enabled', 'timezone', 'windows')}
            if new != {key: before[key] for key in new}:
                row.availability = new
                row.availability_revision += 1
                row.save(update_fields=['availability', 'availability_revision'])
                BusinessAudit.objects.create(
                    actor_id=request.user.pk,
                    object_id=row.pk,
                    action='advisor.availability_updated',
                    metadata={'before': before, 'after': output(row)},
                )
    response = Response(configuration(request.user.pk))
    response['Cache-Control'] = 'no-store'
    return response


def ensure_open(advisor_id, start, end):
    rules = configuration(advisor_id)
    if not rules['enabled']:
        return
    zone = ZoneInfo(rules['timezone'])
    first, last = start.astimezone(zone), end.astimezone(zone)
    if first.date() == last.date() and any(
        row['weekday'] == first.weekday()
        and time.fromisoformat(row['start']) <= first.time()
        and last.time() <= time.fromisoformat(row['end'])
        for row in rules['windows']
    ):
        return
    raise Conflict('Ce créneau est en dehors des disponibilités du conseiller.')


def closed_periods(rules, start, end):
    """Complement of weekly hours for the bounded availability query (at most seven days)."""
    if not rules['enabled']:
        return []
    zone = ZoneInfo(rules['timezone'])
    start, end = start.astimezone(UTC), end.astimezone(UTC)
    day, last_day = start.astimezone(zone).date(), end.astimezone(zone).date()
    windows = []
    while day <= last_day:
        for row in rules['windows']:
            if row['weekday'] != day.weekday():
                continue
            local = [
                datetime.combine(day, time.fromisoformat(row[key])) for key in ('start', 'end')
            ]
            instants = [value.replace(tzinfo=zone).astimezone(UTC) for value in local]
            # Skip nonexistent DST boundaries; never advertise an invented free slot.
            if any(
                value.astimezone(zone).replace(tzinfo=None) != wall
                for value, wall in zip(instants, local)
            ):
                continue
            first, last = max(start, instants[0]), min(end, instants[1])
            if first < last:
                windows.append((first, last))
        day += timedelta(days=1)
    cursor, result = start, []
    for first, last in sorted(windows):
        if first > cursor:
            result.append({'starts_at': cursor, 'ends_at': first, 'reason': 'working_hours'})
        cursor = max(cursor, last)
    if cursor < end:
        result.append({'starts_at': cursor, 'ends_at': end, 'reason': 'working_hours'})
    return result
