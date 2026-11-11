from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, F, Max, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.throttling import UserRateThrottle
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from .mfa import mfa_enabled
from .management_api import AccessPagination
from .models import (
    AccessAudit,
    Membership,
    PhoneCallAttempt,
    PlatformIncident,
    PortalMail,
    ROLES,
    SessionGeneration,
)


def require_superadmin(request):
    if not request.user.is_superuser:
        raise PermissionDenied('Accès réservé au superadministrateur.')
    if settings.MFA_ENABLED and not mfa_enabled(request.user):
        raise PermissionDenied('Activez la double authentification pour accéder à la supervision.')


@api_view(['GET'])
def overview(request):
    require_superadmin(request)
    zone = ZoneInfo('America/Toronto')
    today = timezone.localdate(timezone=zone)
    first = today - timedelta(days=29)
    memberships = Membership.objects.filter(workspace__in=ROLES, active=True, user__is_active=True)
    memberships = memberships.exclude(role='closer')
    attempts = PhoneCallAttempt.objects.filter(
        workspace__in=ROLES,
        created_at__gte=datetime.combine(first, time.min, zone),
        created_at__lt=datetime.combine(today + timedelta(days=1), time.min, zone),
    )
    days = {(first + timedelta(days=i)).isoformat(): dict.fromkeys(ROLES, 0) for i in range(30)}
    for row in (
        attempts.annotate(day=TruncDate('created_at', tzinfo=zone))
        .values('day', 'workspace')
        .annotate(count=Count('pk'))
    ):
        day = row['day'].isoformat()
        if day in days:
            days[day][row['workspace']] = row['count']
    since = timezone.now() - timedelta(hours=24)
    call_incidents = PhoneCallAttempt.objects.filter(
        created_at__gte=since, state__in=('rejected', 'unknown', 'blocked')
    )
    mail_incidents = PortalMail.objects.filter(
        finished_at__gte=since, status__in=('failed', 'expired')
    )
    return Response(
        {
            'memberships': list(
                memberships.values('workspace', 'role').annotate(count=Count('pk'))
            ),
            'days': [{'day': date, **values} for date, values in days.items()],
            'incidents': {
                'calls': list(
                    call_incidents.values('workspace', 'state').annotate(count=Count('pk'))
                ),
                'mail': list(
                    mail_incidents.values('workspace', 'status').annotate(count=Count('pk'))
                ),
                'technical': list(
                    PlatformIncident.objects.filter(created_at__gte=since)
                    .values('area', 'kind', 'status')
                    .annotate(count=Count('pk'), last_seen=Max('created_at'))
                    .order_by('-last_seen')
                ),
            },
            'recent_actions': [
                {
                    'id': row.pk,
                    'action': row.action,
                    'workspace': row.workspace,
                    'actor': row.user.username if row.user else '',
                    'target': row.metadata.get('subject'),
                    'reason': row.metadata.get('reason')
                    or ' '.join(
                        filter(None, (row.metadata.get('method'), row.metadata.get('path')))
                    ),
                    'created_at': row.created_at.isoformat(),
                }
                for row in AccessAudit.objects.filter(action__startswith='platform.')
                .select_related('user')
                .order_by('-pk')[:20]
            ],
        },
        headers={'Cache-Control': 'no-store'},
    )


class IncidentThrottle(UserRateThrottle):
    rate = '20/hour'
    scope = 'platform_incident'


class IncidentInput(serializers.Serializer):
    area = serializers.ChoiceField(choices=('portal', *ROLES))
    kind = serializers.ChoiceField(choices=('http', 'network', 'interface'))
    status = serializers.IntegerField(min_value=500, max_value=599, required=False)

    def validate(self, data):
        if (data['kind'] == 'http') != ('status' in data):
            raise ValidationError('Statut HTTP invalide.')
        return data


@api_view(['GET'])
def incident_details(request):
    require_superadmin(request)
    since = timezone.now() - timedelta(hours=24)
    params = request.query_params
    area, category, kind = (params.get(key) for key in ('area', 'category', 'kind'))
    date_field = 'created_at'
    if category == 'call' and area in ROLES and kind in ('blocked', 'rejected', 'unknown'):
        rows = PhoneCallAttempt.objects.filter(
            workspace=area, state=kind, created_at__gte=since
        ).values('request_id', 'created_at', 'contact_id', 'extension', 'journal_status')
    elif category == 'mail' and kind in ('failed', 'expired'):
        date_field = 'finished_at'
        rows = PortalMail.objects.filter(
            workspace=area, status=kind, finished_at__gte=since
        ).values('id', 'finished_at', 'attempts')
    elif category == 'technical':
        serializer = IncidentInput(
            data={
                'area': area,
                'kind': kind,
                **({'status': params['status']} if 'status' in params else {}),
            }
        )
        serializer.is_valid(raise_exception=True)
        filters = {'status': None, **serializer.validated_data}
        rows = PlatformIncident.objects.filter(created_at__gte=since, **filters).values(
            'id', 'created_at', 'status'
        )
    else:
        raise ValidationError('Catégorie d’incident invalide.')

    pager = AccessPagination()
    page = pager.paginate_queryset(rows.order_by(f'-{date_field}', '-pk'), request)
    response = pager.get_paginated_response(
        [{'observed_at': row.pop(date_field), **row} for row in page]
    )
    response['Cache-Control'] = 'no-store'
    return response


@api_view(['POST'])
@throttle_classes([IncidentThrottle])
def report_platform_incident(request):
    serializer = IncidentInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    PlatformIncident.objects.create(**serializer.validated_data)
    return Response(status=204)


class AdminAction(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=('suspend', 'reactivate', 'revoke_sessions', 'grant_admin', 'suspend_admin')
    )
    workspace = serializers.ChoiceField(choices=tuple(ROLES), required=False)
    reason = serializers.CharField(min_length=3, max_length=500)

    def validate(self, data):
        scoped = data['action'] in ('grant_admin', 'suspend_admin')
        if scoped != ('workspace' in data):
            raise ValidationError('Sélectionnez un espace uniquement pour une action par espace.')
        return data


@api_view(['GET'])
def platform_accounts(request):
    require_superadmin(request)
    query = request.query_params.get('search', '').strip()[:150]
    users = get_user_model().objects.exclude(username__startswith='deleted-')
    if query:
        users = users.filter(Q(username__icontains=query) | Q(email__icontains=query))
    else:
        users = users.filter(
            Q(workspace_memberships__role='administrator') | Q(is_superuser=True)
        ).distinct()
    pager = AccessPagination()
    rows = pager.paginate_queryset(
        users.order_by('username', 'pk').prefetch_related('workspace_memberships'), request
    )
    result = pager.get_paginated_response(
        [
            {
                'id': row.pk,
                'username': row.username,
                'email': row.email,
                'active': row.is_active,
                'protected': row.is_superuser or row.is_staff,
                'memberships': [
                    {'workspace': grant.workspace, 'role': grant.role, 'active': grant.active}
                    for grant in row.workspace_memberships.all()
                ],
            }
            for row in rows
        ]
    )
    result['Cache-Control'] = 'no-store'
    return result


@api_view(['POST'])
def platform_account_action(request, pk):
    require_superadmin(request)
    serializer = AdminAction(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    action = data['action']
    workspace = data.get('workspace', '')
    with transaction.atomic():
        target = get_user_model().objects.select_for_update().filter(pk=pk).first()
        if not target or target.username.startswith('deleted-'):
            raise NotFound('Compte introuvable.')
        if target.is_superuser or target.is_staff or target.pk == request.user.pk:
            raise PermissionDenied('Ce compte système est protégé.')
        if workspace:
            grant = (
                Membership.objects.select_for_update()
                .filter(user=target, workspace=workspace)
                .first()
            )
            if action == 'grant_admin':
                if grant and grant.role != 'administrator':
                    raise ValidationError(
                        'Modifiez le rôle métier existant dans la gestion de cet espace.'
                    )
                if not target.is_active:
                    raise ValidationError('Réactivez le compte avant de lui attribuer un accès.')
                if grant:
                    grant.active = True
                    grant.save(update_fields=['active'])
                else:
                    Membership.objects.create(
                        user=target, workspace=workspace, role='administrator'
                    )
            else:
                if not grant or grant.role != 'administrator':
                    raise ValidationError('Ce compte n’est pas administrateur de cet espace.')
                grant.active = False
                grant.save(update_fields=['active'])
        elif action in ('suspend', 'reactivate'):
            target.is_active = action == 'reactivate'
            target.save(update_fields=['is_active'])
        if action in ('suspend', 'suspend_admin', 'revoke_sessions'):
            SessionGeneration.objects.get_or_create(user=target)
            SessionGeneration.objects.filter(user=target).update(generation=F('generation') + 1)
        AccessAudit.objects.create(
            user=request.user,
            action='platform.' + action,
            workspace=workspace,
            metadata={'subject': target.pk, 'reason': data['reason']},
        )
    return Response(status=204, headers={'Cache-Control': 'no-store'})
