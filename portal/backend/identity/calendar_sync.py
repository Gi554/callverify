"""One-way, opt-in publication. Business APIs remain authoritative and databases independent."""

import hashlib
import json
from datetime import timedelta
from urllib.parse import urlsplit
from uuid import uuid4
import requests
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.decorators import api_view, throttle_classes
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from packages.access.tickets import issue
from packages.calendar_connectors import providers, events
from .models import CalendarConnection, CalendarSync, AccessAudit
from .calendars import (
    require_owner,
    config,
    unseal,
    seal,
    StrictInput,
    validated,
    Unavailable,
    CalendarThrottle,
    OWNERS,
)
from .passwords import PasswordThrottle
from django.contrib.auth import get_user_model

ERRORS = {
    'provider_unavailable',
    'slot_busy',
    'event_changed',
    'event_has_attendees',
    'uncertain_create',
    'source_unavailable',
    'source_changed',
    'past_source',
}


def fetch_source(user, workspace, source_id=None, page=1):
    require_owner(user, workspace)
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
        raise Unavailable()
    path = '/api/assurance/appointments/' if workspace == 'assurance' else '/api/visits/'
    if source_id:
        path += str(source_id) + '/'
    else:
        path += f'?period=upcoming&page={page}'
    try:
        response = requests.get(
            base + path,
            headers={
                'Authorization': 'Bearer ' + issue(user.pk, workspace, OWNERS[workspace]),
                'X-Forwarded-Proto': 'https',
            },
            timeout=10,
            allow_redirects=False,
        )
        if response.status_code != 200 or len(response.content) > 2_000_000:
            raise Unavailable()
        data = response.json()
        if not isinstance(data, dict):
            raise Unavailable()
        return data
    except (requests.RequestException, ValueError):
        raise Unavailable() from None


def source(user, workspace, pk):
    row = fetch_source(user, workspace, pk)
    if workspace == 'assurance' and row.get('calendar') in ('calendly', 'external_link'):
        # The external booking tool already owns this event: never publish a second copy.
        row['status'] = 'cancelled'
    owner = row.get('advisor' if workspace == 'assurance' else 'client')
    if not isinstance(owner, dict) or owner.get('id') != user.pk or row.get('id') != pk:
        raise Unavailable()
    if (
        row.get('status') not in ('scheduled', 'cancelled')
        or type(row.get('revision')) is not int
        or row['revision'] < 0
    ):
        raise Unavailable()
    try:
        first = providers.instant(row.get('starts_at'))
        last = providers.instant(row.get('ends_at'))
    except providers.ProviderError:
        raise Unavailable() from None
    if not timedelta(0) < last - first <= timedelta(days=31):
        raise Unavailable()
    return {
        'id': pk,
        'isolation_publication': workspace == 'isolation' and row.get('calendar') == 'google',
        'revision': row['revision'],
        'status': row['status'],
        'starts_at': first,
        'ends_at': last,
    }


def fingerprint(row):
    return hashlib.sha256(
        json.dumps(
            {
                'status': row['status'],
                'start': row['starts_at'].isoformat(),
                'end': row['ends_at'].isoformat(),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()


def credential(connection):
    options = config(connection.provider)
    tokens = unseal(connection.payload)
    if not isinstance(tokens, dict) or not tokens.get('access') or not tokens.get('refresh'):
        raise providers.ProviderError(True)
    if connection.expires_at is None or connection.expires_at <= timezone.now() + timedelta(
        seconds=60
    ):
        tokens, seconds = providers.tokens(connection.provider, options, refresh=tokens['refresh'])
        connection.payload = seal(tokens)
        connection.expires_at = timezone.now() + timedelta(seconds=seconds)
        connection.save(update_fields=['payload', 'expires_at'])
    return tokens['access']


def _sync_one(connection, pk, withdraw=False):
    user = connection.user
    workspace = connection.workspace
    require_owner(user, workspace)
    target = None if withdraw else source(user, workspace, pk)
    # Commit the creation key/intent before any external write. A crash cannot erase it.
    with transaction.atomic():
        if not CalendarConnection.objects.filter(pk=connection.pk, connected=True).update(
            revision=F('revision')
        ):
            raise Unavailable()
        connection.refresh_from_db()
        if not withdraw and not connection.auto_sync:
            return 'paused'
        ledger = CalendarSync.objects.filter(connection=connection, source_id=pk).first()
        if ledger is None:
            if withdraw or target['status'] == 'cancelled' or target['ends_at'] <= timezone.now():
                return 'skipped'
            ledger = CalendarSync.objects.create(
                connection=connection,
                source_id=pk,
                provider=connection.provider,
                expected_start=target['starts_at'],
                expected_end=target['ends_at'],
            )
        if ledger.status in ('removed', 'abandoned'):
            if withdraw or target['status'] == 'cancelled':
                return 'removed'
            ledger.key = uuid4()
            ledger.remote_id = ''
            ledger.provider = connection.provider
            ledger.status = 'pending'
            ledger.create_attempted = False
            ledger.expected_start = target['starts_at']
            ledger.expected_end = target['ends_at']
        if target is not None and target.get('isolation_publication'):
            ledger.isolation_publication = True
            ledger.source_revision = target['revision']
        first_attempt = not ledger.create_attempted
        if not withdraw:
            ledger.create_attempted = True
        ledger.save()
        key = ledger.key
    with transaction.atomic():
        CalendarConnection.objects.filter(pk=connection.pk).update(revision=F('revision'))
        connection.refresh_from_db()
        ledger = CalendarSync.objects.get(pk=ledger.pk)
        if ledger.key != key or ledger.status in ('removed', 'abandoned'):
            return 'skipped'
        if not connection.connected or (not withdraw and not connection.auto_sync):
            return 'paused'
        if ledger.provider != connection.provider:
            raise Unavailable()
        require_owner(user, workspace)
        remote = None
        try:
            access = credential(connection)
            remote = events.find(connection.provider, access, ledger.key)
            target = None if withdraw else source(user, workspace, pk)
            if target is not None:
                ledger.source_revision = target['revision']
            if withdraw or target['status'] == 'cancelled':
                if (
                    remote is None
                    and ledger.create_attempted
                    and not ledger.remote_id
                    and not first_attempt
                ):
                    raise providers.ProviderError(code='uncertain_create')
                events.remove(connection.provider, access, remote)
                ledger.status = 'removed'
                ledger.error_code = ''
            else:
                if target['ends_at'] <= timezone.now() and remote is None:
                    raise providers.ProviderError(code='past_source')
                if remote is None and not first_attempt:
                    raise providers.ProviderError(code='uncertain_create')
                if remote:
                    actual = events.interval(connection.provider, remote)
                    if actual != (ledger.expected_start, ledger.expected_end):
                        raise providers.ProviderError(code='event_changed')
                    ledger.remote_id = remote['id']
                digest = fingerprint(target)
                if remote is None or digest != ledger.fingerprint:
                    ledger.remote_id = events.publish(
                        connection.provider, access, ledger.key, workspace, target, remote
                    )
                    ledger.expected_start = target['starts_at']
                    ledger.expected_end = target['ends_at']
                ledger.fingerprint = digest
                ledger.source_revision = target['revision']
                ledger.status = 'synced'
                ledger.error_code = ''
                if fingerprint(source(user, workspace, pk)) != digest:
                    ledger.status = 'pending'
                    ledger.error_code = 'source_changed'
        except providers.ProviderError as error:
            ledger.status = 'error'
            ledger.error_code = error.code if error.code in ERRORS else 'provider_unavailable'
            if error.code == 'slot_busy' and remote is None:
                ledger.create_attempted = False
            if error.reauthorize:
                connection.connected = False
                connection.payload = ''
                connection.expires_at = None
                connection.auto_sync = False
                connection.revision += 1
                connection.save(
                    update_fields=['connected', 'payload', 'expires_at', 'auto_sync', 'revision']
                )
        except Unavailable:
            ledger.status = 'error'
            ledger.error_code = 'source_unavailable'
        ledger.checked_at = timezone.now()
        ledger.save()
        AccessAudit.objects.create(
            user=user,
            workspace=workspace,
            action='calendar.event_checked',
            metadata={'source_id': pk, 'status': ledger.status, 'error_code': ledger.error_code},
        )
        return ledger.status


def sync_one(connection, pk, withdraw=False):
    state = _sync_one(connection, pk, withdraw)
    if connection.workspace == 'isolation':
        from .isolation_publication import feedback

        if not feedback(connection, pk):
            return 'feedback_pending'
    return state


def sync_connection(connection):
    require_owner(connection.user, connection.workspace)
    ids = set()
    # Known cancellations/past events are fetched individually; never infer cancellation from absence in a list.
    ids.update(
        CalendarSync.objects.filter(connection=connection)
        .exclude(status__in=['removed', 'abandoned'])
        .values_list('source_id', flat=True)
    )
    for page in range(1, 201):
        data = fetch_source(connection.user, connection.workspace, page=page)
        rows = data.get('results')
        if not isinstance(rows, list) or len(rows) > 25:
            raise Unavailable()
        for row in rows:
            if not isinstance(row, dict) or type(row.get('id')) is not int or row['id'] < 1:
                raise Unavailable()
            ids.add(row['id'])
        if not data.get('next'):
            break
    else:
        raise Unavailable()
    counts = {}
    for pk in sorted(ids):
        state = sync_one(connection, pk)
        counts[state] = counts.get(state, 0) + 1
    return counts


class Toggle(StrictInput):
    revision = serializers.IntegerField(min_value=0)
    enabled = serializers.BooleanField()


@api_view(['POST'])
@throttle_classes([CalendarThrottle])
def configure(request, workspace):
    require_owner(request.user, workspace)
    data = validated(Toggle, request.data)
    with transaction.atomic():
        qs = CalendarConnection.objects.filter(
            user=request.user, workspace=workspace, connected=True, revision=data['revision']
        )
        if not qs.update(auto_sync=data['enabled'], revision=F('revision') + 1):
            raise ValidationError('Connexion modifiée : actualisez')
        AccessAudit.objects.create(
            user=request.user,
            workspace=workspace,
            action='calendar.sync_configured',
            metadata={'enabled': data['enabled']},
        )
    return Response(status=204)


@api_view(['GET', 'POST'])
@throttle_classes([CalendarThrottle])
def synchronization(request, workspace):
    require_owner(request.user, workspace)
    connection = (
        CalendarConnection.objects.filter(user=request.user, workspace=workspace)
        .select_related('user')
        .first()
    )
    if not connection:
        raise ValidationError('Connectez votre agenda')
    if request.method == 'POST':
        if request.data:
            raise ValidationError('Aucun paramètre attendu')
        if not connection.connected or not connection.auto_sync:
            raise ValidationError('Activez la synchronisation avant de la lancer')
        return Response({'counts': sync_connection(connection)})
    from .management_api import AccessPagination

    pager = AccessPagination()
    rows = pager.paginate_queryset(connection.events.order_by('-pk'), request)
    response = pager.get_paginated_response(
        [
            {
                'source_id': row.source_id,
                'provider': row.provider,
                'status': row.status,
                'error_code': row.error_code,
                'source_revision': row.source_revision,
                'checked_at': row.checked_at,
            }
            for row in rows
        ]
    )
    response['Cache-Control'] = 'no-store'
    return response


@api_view(['POST'])
@throttle_classes([CalendarThrottle])
def withdraw_all(request, workspace):
    require_owner(request.user, workspace)
    if request.data != {'confirm': True}:
        raise ValidationError('Confirmation explicite requise')
    connection = (
        CalendarConnection.objects.filter(user=request.user, workspace=workspace, connected=True)
        .select_related('user')
        .first()
    )
    if not connection:
        raise ValidationError('Agenda non connecté')
    CalendarConnection.objects.filter(pk=connection.pk).update(
        auto_sync=False, revision=F('revision') + 1
    )
    counts = {}
    for pk in (
        connection.events.exclude(status__in=['removed', 'abandoned'])
        .order_by('source_id')
        .values_list('source_id', flat=True)
    ):
        state = sync_one(connection, pk, withdraw=True)
        counts[state] = counts.get(state, 0) + 1
    return Response({'counts': counts})


class DetachInput(StrictInput):
    current_password = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True)
    revision = serializers.IntegerField(min_value=0)
    confirm_external_cleanup = serializers.BooleanField()


@api_view(['POST'])
@throttle_classes([PasswordThrottle])
def detach(request, workspace):
    require_owner(request.user, workspace)
    data = validated(DetachInput, request.data)
    if not data['confirm_external_cleanup']:
        raise ValidationError(
            'Vérifiez et retirez manuellement les anciens événements externes avant de confirmer'
        )
    with transaction.atomic():
        users = get_user_model().objects.filter(pk=request.user.pk, is_active=True)
        if not users.update(password=F('password')):
            raise ValidationError('Compte indisponible')
        if not users.get().check_password(data['current_password']):
            raise ValidationError('Mot de passe actuel incorrect')
        require_owner(request.user, workspace)
        qs = CalendarConnection.objects.filter(
            user=request.user, workspace=workspace, revision=data['revision']
        )
        if not qs.update(
            auto_sync=False,
            connected=False,
            payload='',
            expires_at=None,
            revision=F('revision') + 1,
        ):
            raise ValidationError('Connexion modifiée : actualisez')
        connection = CalendarConnection.objects.get(user=request.user, workspace=workspace)
        count = connection.events.exclude(status__in=['removed', 'abandoned']).update(
            status='abandoned', error_code='', checked_at=timezone.now()
        )
        from .models import CalendarAuthorization

        CalendarAuthorization.objects.filter(
            user=request.user, workspace=workspace, used=False
        ).update(used=True, verifier='')
        AccessAudit.objects.create(
            user=request.user,
            workspace=workspace,
            action='calendar.manual_cleanup_acknowledged',
            metadata={'records': count, 'provider': connection.provider},
        )
    response = Response(status=204)
    response['Cache-Control'] = 'no-store'
    return response
