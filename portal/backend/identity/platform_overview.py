from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from .mfa import mfa_enabled
from .models import Membership, PhoneCallAttempt, ROLES


@api_view(['GET'])
def overview(request):
    if not request.user.is_superuser:
        raise PermissionDenied('Accès réservé au superadministrateur.')
    if settings.MFA_ENABLED and not mfa_enabled(request.user):
        raise PermissionDenied('Activez la double authentification pour accéder à la supervision.')

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
    return Response(
        {
            'memberships': list(memberships.values('workspace', 'role').annotate(count=Count('pk'))),
            'days': [{'day': date, **values} for date, values in days.items()],
        },
        headers={'Cache-Control': 'no-store'},
    )
