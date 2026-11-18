from collections import defaultdict
from datetime import timedelta
from math import ceil
from statistics import median

from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from .models import Membership, PerformanceSample


class Sample(serializers.Serializer):
    area = serializers.ChoiceField(choices=('assurance', 'isolation'))
    operation = serializers.ChoiceField(
        choices=('column', 'contact', 'qualification', 'booking', 'board', 'send', 'first', 'open')
    )
    elapsed_ms = serializers.IntegerField(min_value=0, max_value=600000)
    server_ms = serializers.IntegerField(min_value=0, max_value=600000, allow_null=True)
    sql_ms = serializers.IntegerField(min_value=0, max_value=600000, allow_null=True)
    failed = serializers.BooleanField()


class SampleThrottle(UserRateThrottle):
    rate = '120/min'
    scope = 'setter_performance_samples'


@api_view(['POST'])
@throttle_classes([SampleThrottle])
def collect(request):
    samples = Sample(data=request.data, many=True, max_length=40, allow_empty=False)
    samples.is_valid(raise_exception=True)
    areas = {row['area'] for row in samples.validated_data}
    allowed = Membership.objects.filter(user=request.user, active=True, role='setter').values_list(
        'workspace', flat=True
    )
    if not areas.issubset(allowed):
        raise PermissionDenied()
    PerformanceSample.objects.bulk_create(
        [PerformanceSample(**row) for row in samples.validated_data]
    )
    expired = list(
        PerformanceSample.objects.filter(
            created_at__lt=timezone.now() - timedelta(days=1)
        ).values_list('pk', flat=True)[:80]
    )
    if expired:
        PerformanceSample.objects.filter(pk__in=expired).delete()
    return Response(status=204)


def recent_performance(since):
    groups = defaultdict(list)
    for sample in PerformanceSample.objects.filter(created_at__gte=since).order_by('-pk')[:5000]:
        groups[sample.area, sample.operation].append(sample)
    result = []
    for (area, operation), rows in sorted(groups.items()):
        elapsed = sorted(row.elapsed_ms for row in rows if not row.failed)
        servers = [row.server_ms for row in rows if not row.failed and row.server_ms is not None]
        sql = [row.sql_ms for row in rows if not row.failed and row.sql_ms is not None]
        result.append(
            dict(
                area=area,
                operation=operation,
                total=len(rows),
                errors=len(rows) - len(elapsed),
                median_ms=round(median(elapsed)) if elapsed else None,
                p95_ms=elapsed[ceil(len(elapsed) * 0.95) - 1] if elapsed else None,
                server_ms=round(median(servers)) if servers else None,
                sql_ms=round(median(sql)) if sql else None,
            )
        )
    return result
