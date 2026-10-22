"""Read-only, service-authenticated availability for CRM confirmations."""

from django.contrib.auth import get_user_model
from django.core import signing
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.response import Response
from packages.access.calendar_checks import verify
from packages.calendar_connectors import providers, events
from .models import Membership, CalendarConnection, CalendarSync, AccessAudit
from .calendars import Unavailable, CalendarThrottle
from .calendar_sync import credential


def active(pk, role, workspace):
    return Membership.objects.filter(
        user_id=pk, user__is_active=True, workspace=workspace, role=role, active=True
    ).exists()


def check(data, workspace='assurance'):
    owner_role = 'advisor' if workspace == 'assurance' else 'client'
    if not active(data['actor'], data['role'], workspace) or not active(
        data['owner'], owner_role, workspace
    ):
        raise PermissionDenied('Participants actifs requis.')
    owner = get_user_model().objects.get(pk=data['owner'])
    failure = False
    with transaction.atomic():
        row, _ = CalendarConnection.objects.get_or_create(user=owner, workspace=workspace)
        CalendarConnection.objects.filter(pk=row.pk).update(revision=F('revision'))
        row.refresh_from_db()
        result = 'internal_only'
        # A previously linked account must be reconnected, never treated as free.
        if row.provider and not row.connected:
            raise Unavailable()
        if row.connected:
            try:
                access = credential(row)
                exclude = None
                if data['source_id'] is not None:
                    ledger = (
                        CalendarSync.objects.filter(connection=row, source_id=data['source_id'])
                        .exclude(status__in=['removed', 'abandoned'])
                        .first()
                    )
                    if ledger:
                        if (
                            ledger.status != 'synced'
                            or ledger.provider != row.provider
                            or not ledger.remote_id
                        ):
                            raise providers.ProviderError()
                        remote = events.find(row.provider, access, ledger.key)
                        if (
                            remote is None
                            or remote['id'] != ledger.remote_id
                            or events.interval(row.provider, remote)
                            != (ledger.expected_start, ledger.expected_end)
                        ):
                            raise providers.ProviderError()
                        exclude = remote['id']
                periods = providers.busy(
                    row.provider, access, data['start'], data['end'], exclude_id=exclude
                )
                result = 'busy' if periods else 'free'
            except providers.ProviderError as error:
                failure = True
                if error.reauthorize:
                    row.connected = False
                    row.auto_sync = False
                    row.payload = ''
                    row.expires_at = None
                    row.revision += 1
                    row.save(
                        update_fields=[
                            'connected',
                            'auto_sync',
                            'payload',
                            'expires_at',
                            'revision',
                        ]
                    )
        if not active(data['actor'], data['role'], workspace) or not active(
            data['owner'], owner_role, workspace
        ):
            raise PermissionDenied('Participants modifiés.')
        checked_at = timezone.now().isoformat()
        AccessAudit.objects.create(
            user_id=data['actor'],
            workspace=workspace,
            action='calendar.booking_checked',
            metadata={
                'owner_id': owner.pk,
                'source_id': data['source_id'],
                'result': 'unavailable' if failure else result,
            },
        )
    if failure:
        raise Unavailable()
    return {'result': result, 'checked_at': checked_at}


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([CalendarThrottle])
def availability(request, workspace='assurance'):
    if (
        request.query_params
        or not isinstance(request.data, dict)
        or set(request.data) != {'proof'}
        or not isinstance(request.data['proof'], str)
        or len(request.data['proof']) > 8192
    ):
        raise ValidationError('Preuve serveur seule requise.')
    try:
        data = verify(request.data['proof'], workspace)
    except (signing.BadSignature, TypeError, ValueError, AttributeError):
        raise PermissionDenied('Preuve serveur invalide ou expirée.') from None
    response = Response(check(data, workspace))
    response['Cache-Control'] = 'no-store'
    return response
