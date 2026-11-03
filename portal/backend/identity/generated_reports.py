"""Durable report schedule and immutable downloads, confined to the active workspace."""

from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from uuid import uuid4
from django.db import transaction
from django.db.models import Q, F
from django.http import HttpResponse
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.response import Response
from packages.quebec_period import ZONE, period
from packages.pdf_exports import document
from .models import ReportPlan, GeneratedReport, Membership, AccessAudit
from .management_api import require_admin, lock_admin
from .report_sources import snapshot

KINDS = {
    'performance': 'Performance des agents',
    'campaigns': 'Campagnes et lots',
}
MAX_BYTES = 10_000_000


def audit(workspace, actor, action, metadata):
    AccessAudit.objects.create(
        workspace=workspace,
        user_id=actor,
        action='report.' + action,
        metadata={'actor_id': actor, **metadata},
    )


def dates(cadence, day):
    if cadence == 'daily':
        return day - timedelta(days=1), day - timedelta(days=1)
    if cadence == 'weekly':
        return day - timedelta(days=7), day - timedelta(days=1)
    last = day.replace(day=1) - timedelta(days=1)
    return last.replace(day=1), last


def schedule(now=None):
    now = now or timezone.now()
    local = now.astimezone(ZONE)
    made = 0
    for plan in ReportPlan.objects.filter(enabled=True):
        if local.hour < plan.hour:
            continue
        if not Membership.objects.filter(
            user_id=plan.actor_id,
            workspace=plan.workspace,
            role='administrator',
            active=True,
            user__is_active=True,
        ).exists():
            continue
        for cadence in (
            ['daily']
            + (['weekly'] if local.weekday() == 0 else [])
            + (['monthly'] if local.day == 1 else [])
        ):
            first, last = dates(cadence, local.date())
            for kind in KINDS:
                with transaction.atomic():
                    job, created = GeneratedReport.objects.get_or_create(
                        event_key=f'{plan.workspace}:{cadence}:{kind}:{first}:{last}',
                        defaults={
                            'workspace': plan.workspace,
                            'kind': kind,
                            'cadence': cadence,
                            'starts_on': first,
                            'ends_on': last,
                            'actor_id': plan.actor_id,
                        },
                    )
                    made += created
                    if created:
                        audit(
                            plan.workspace,
                            plan.actor_id,
                            'requested',
                            {'report_id': job.pk, 'kind': kind, 'cadence': cadence},
                        )
    return made


def claim(now=None):
    now = now or timezone.now()
    GeneratedReport.objects.filter(state='running', lease_until__lte=now, attempts__gte=3).update(
        state='failed', error_code='attempts_exhausted', lease_until=None
    )
    eligible = (
        Q(state='queued')
        | Q(state='failed', attempts__lt=3, retry_at__lte=now)
        | Q(state='running', lease_until__lte=now, attempts__lt=3)
    )
    for pk in (
        GeneratedReport.objects.filter(eligible)
        .order_by('created_at')
        .values_list('pk', flat=True)[:10]
    ):
        token = uuid4()
        with transaction.atomic():
            if GeneratedReport.objects.filter(eligible, pk=pk).update(
                state='running',
                lease_token=token,
                lease_until=now + timedelta(minutes=10),
                attempts=F('attempts') + 1,
            ):
                job = GeneratedReport.objects.get(pk=pk)
                audit(
                    job.workspace,
                    job.actor_id,
                    'started',
                    {'report_id': job.pk, 'attempt': job.attempts, 'source': 'worker'},
                )
                return job
    return None


def xlsx(data):
    book = Workbook()
    sheet = book.active
    sheet.title = 'Rapport'
    sheet.append(['ORVIA CRM', KINDS.get(data['kind'], data['kind'])])
    sheet.append(['Espace', data['workspace']])
    sheet.append(['Du (Québec)', data['from']])
    sheet.append(['Au inclus (Québec)', data['to']])
    sheet.append(['Règle', data['definition']])
    sheet.append(data['headers'])
    sheet.freeze_panes = 'A7'
    for row in data['rows']:
        values = []
        for header, value in zip(data['headers'], row):
            if 'CAD' in header and value != 'Non disponible':
                value = Decimal(str(value))
            values.append(value)
        sheet.append(values)
    for row in sheet:
        for cell in row:
            if isinstance(cell.value, str):
                cell.data_type = 's'
    for cell in sheet[6]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='6250CB')
    sheet.auto_filter.ref = f'A6:{sheet.cell(sheet.max_row,sheet.max_column).coordinate}'
    for column in sheet.columns:
        sheet.column_dimensions[column[0].column_letter].width = 25
    sheet.column_dimensions['B'].width = 40
    stream = BytesIO()
    book.save(stream)
    return stream.getvalue()


def generate(job):
    if not GeneratedReport.objects.filter(
        pk=job.pk, state='running', lease_token=job.lease_token
    ).exists():
        return False
    try:
        if not Membership.objects.filter(
            user_id=job.actor_id,
            workspace=job.workspace,
            role='administrator',
            active=True,
            user__is_active=True,
        ).exists():
            raise ValueError('Actor revoked')
        data = job.snapshot or snapshot(job)
        # Preserve captured values before file generation so retries do not change a report.
        updated = GeneratedReport.objects.filter(
            pk=job.pk, state='running', lease_token=job.lease_token
        ).update(snapshot=data)
        if not updated:
            return False
        pdf = document(
            KINDS.get(job.kind, job.kind),
            data['headers'],
            data['rows'],
            f"{job.workspace.upper()} - Du {job.starts_on} au {job.ends_on}. {data['definition']}",
        )
        excel = xlsx(data)
        if max(len(pdf), len(excel)) > MAX_BYTES:
            raise ValueError('Report too large')
        with transaction.atomic():
            changed = GeneratedReport.objects.filter(
                pk=job.pk, state='running', lease_token=job.lease_token
            ).update(
                state='succeeded',
                pdf_data=pdf,
                xlsx_data=excel,
                completed_at=timezone.now(),
                lease_until=None,
                error_code='',
            )
            if changed:
                audit(
                    job.workspace,
                    job.actor_id,
                    'completed',
                    {'report_id': job.pk, 'kind': job.kind, 'rows': len(data['rows'])},
                )
        return bool(changed)
    except Exception:
        with transaction.atomic():
            changed = GeneratedReport.objects.filter(
                pk=job.pk, state='running', lease_token=job.lease_token
            ).update(
                state='failed',
                error_code='generation_failed',
                retry_at=timezone.now() + timedelta(minutes=5),
                lease_until=None,
            )
            if changed:
                audit(
                    job.workspace,
                    job.actor_id,
                    'failed',
                    {
                        'report_id': job.pk,
                        'attempt': job.attempts,
                        'error_code': 'generation_failed',
                        'source': 'worker',
                    },
                )
        return False


class PlanInput(serializers.Serializer):
    enabled = serializers.BooleanField()
    hour = serializers.IntegerField(min_value=0, max_value=23)
    revision = serializers.IntegerField(min_value=0)


def plan_output(plan):
    return {
        'enabled': plan.enabled if plan else False,
        'hour': plan.hour if plan else 19,
        'revision': plan.revision if plan else 0,
        'timezone': 'America/Toronto',
        'authorized': not plan
        or Membership.objects.filter(
            user_id=plan.actor_id,
            workspace=plan.workspace,
            role='administrator',
            active=True,
            user__is_active=True,
        ).exists(),
    }


@api_view(['GET', 'POST'])
def plans(request, workspace):
    require_admin(request.user, workspace)
    if request.method == 'GET':
        return Response(plan_output(ReportPlan.objects.filter(workspace=workspace).first()))
    serializer = PlanInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    with transaction.atomic():
        lock_admin(request.user, workspace)
        plan = ReportPlan.objects.filter(workspace=workspace).first()
        if (plan.revision if plan else 0) != data['revision']:
            raise ValidationError('Plan modifié : rechargez avant de sauvegarder.')
        before = plan_output(plan)
        plan, _ = ReportPlan.objects.update_or_create(
            workspace=workspace,
            defaults={
                'enabled': data['enabled'],
                'hour': data['hour'],
                'actor_id': request.user.pk,
                'revision': data['revision'] + 1,
            },
        )
        audit(
            workspace,
            request.user.pk,
            'plan_updated',
            {'before': before, 'after': plan_output(plan)},
        )
    return Response(plan_output(plan))


class ReportInput(serializers.Serializer):
    kind = serializers.ChoiceField(choices=list(KINDS))
    request_id = serializers.UUIDField()
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()


def output(row):
    return {
        key: getattr(row, key)
        for key in (
            'id',
            'kind',
            'cadence',
            'starts_on',
            'ends_on',
            'state',
            'attempts',
            'error_code',
            'created_at',
            'completed_at',
            'actor_id',
        )
    }


@api_view(['GET', 'POST'])
def reports(request, workspace):
    require_admin(request.user, workspace)
    if request.method == 'POST':
        data = ReportInput(data=request.data)
        data.is_valid(raise_exception=True)
        data = data.validated_data
        period({'from': str(data['starts_on']), 'to': str(data['ends_on'])})
        if data['ends_on'] > timezone.now().astimezone(ZONE).date():
            raise ValidationError('La période ne peut pas dépasser aujourd’hui au Québec.')
        key = f"{workspace}:manual:{data['request_id']}"
        with transaction.atomic():
            lock_admin(request.user, workspace)
            previous = GeneratedReport.objects.filter(event_key=key).first()
            if previous:
                if any(getattr(previous, k) != data[k] for k in ('kind', 'starts_on', 'ends_on')):
                    raise ValidationError('Demande déjà utilisée pour un autre rapport.')
                return Response(output(previous))
            if (
                GeneratedReport.objects.filter(
                    workspace=workspace,
                    actor_id=request.user.pk,
                    created_at__gte=timezone.now() - timedelta(minutes=1),
                    cadence='manual',
                ).count()
                >= 5
            ):
                raise ValidationError('Maximum cinq demandes manuelles par minute.')
            row = GeneratedReport.objects.create(
                event_key=key,
                workspace=workspace,
                actor_id=request.user.pk,
                cadence='manual',
                **{k: data[k] for k in ('kind', 'starts_on', 'ends_on')},
            )
            audit(workspace, request.user.pk, 'requested', {'report_id': row.pk, 'kind': row.kind})
        return Response(output(row), status=201)
    try:
        page = int(request.query_params.get('page', '1'))
        if not 1 <= page <= 1000000:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValidationError('Page invalide.') from None
    rows = (
        GeneratedReport.objects.filter(workspace=workspace)
        .defer('snapshot', 'pdf_data', 'xlsx_data')
        .order_by('-created_at', '-pk')
    )
    result = Response(
        {
            'count': rows.count(),
            'results': [output(row) for row in rows[(page - 1) * 25 : page * 25]],
            'page': page,
            'timezone': 'America/Toronto',
        }
    )
    result['Cache-Control'] = 'no-store'
    return result


@api_view(['GET'])
def download(request, workspace, pk, file_kind):
    require_admin(request.user, workspace)
    if file_kind not in ('pdf', 'xlsx'):
        raise ValidationError('Format PDF ou Excel requis.')
    field = file_kind + '_data'
    row = (
        GeneratedReport.objects.filter(pk=pk, workspace=workspace, state='succeeded')
        .only('id', 'kind', 'starts_on', 'ends_on', field)
        .first()
    )
    if row is None:
        raise NotFound('Rapport terminé introuvable dans cet espace.')
    audit(workspace, request.user.pk, 'downloaded', {'report_id': pk, 'format': file_kind})
    result = HttpResponse(
        bytes(getattr(row, field)),
        content_type='application/pdf'
        if file_kind == 'pdf'
        else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    result['Content-Disposition'] = (
        f'attachment; filename="orvia-{workspace}-{row.kind}-{row.starts_on}-{row.ends_on}.{file_kind}"'
    )
    result['Cache-Control'] = 'no-store'
    result['X-Content-Type-Options'] = 'nosniff'
    return result


@api_view(['GET'])
def history(request, workspace, pk):
    require_admin(request.user, workspace)
    if not GeneratedReport.objects.filter(pk=pk, workspace=workspace).exists():
        raise NotFound('Rapport introuvable.')
    rows = AccessAudit.objects.filter(
        workspace=workspace, action__startswith='report.', metadata__report_id=pk
    ).order_by('-created_at', '-pk')[:100]
    result = Response(
        {
            'results': [
                {
                    'id': r.pk,
                    'action': r.action,
                    'actor_id': r.metadata.get('actor_id', r.user_id),
                    'created_at': r.created_at,
                    'metadata': r.metadata,
                }
                for r in rows
            ]
        }
    )
    result['Cache-Control'] = 'no-store'
    return result
