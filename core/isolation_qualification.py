"""Isolation-only import, Lookup and export flow for the central CRM."""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.http import FileResponse
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .delivery import enqueue
from .isolation_work import Pager, WorkAuthentication
from .models import AdminUser, AuditEvent, Campaign, ExportJob, ImportBatch, LookupCheck, Prospect
from .serializers import ExportSerializer, ImportSerializer, ProspectSerializer
from .services import EXPORT_COLUMNS, FILTERS, read_table, schedule_lookup


WORKSPACE = 'isolation'


def service_owner():
    """Technical FK owner only; central actor ids stay in the audit trail."""
    user, created = AdminUser.objects.get_or_create(
        username='__isolation_qualification_service__',
        defaults={'is_active': False, 'is_staff': False, 'is_superuser': False},
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=['password'])
    return user


def audit(request, action, obj=None, **metadata):
    AuditEvent.objects.create(
        action=action,
        object_id=str(obj.pk) if obj else '',
        metadata={'actor_portal_id': request.user.pk, 'workspace': WORKSPACE, **metadata},
    )


class QualificationAuthentication(WorkAuthentication):
    roles = ('administrator',)


class CampaignInput(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    purpose = serializers.CharField(required=False, allow_blank=True, max_length=5000)
    source = serializers.CharField(required=False, allow_blank=True, max_length=250)
    budget = serializers.DecimalField(max_digits=12, decimal_places=4, required=False, min_value=0)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés')
        return data


def campaign_output(campaign):
    phones = campaign.prospects.filter(phone__isnull=False).count()
    checks = LookupCheck.objects.filter(campaign=campaign)
    completed = checks.filter(status='completed').values('phone_id').distinct().count()
    return {
        'id': campaign.pk,
        'name': campaign.name,
        'purpose': campaign.purpose,
        'source': campaign.source,
        'status': campaign.status,
        'budget': str(campaign.budget),
        'spent': str(campaign.spent),
        'created_at': campaign.created_at,
        'progress': {
            'total': phones,
            'checked': completed,
            'pending': checks.filter(status__in=('pending', 'running')).count(),
            'errors': checks.filter(status='error').count(),
            'percent': min(100, round(100 * completed / phones)) if phones else 0,
        },
    }


class QualificationViewSet(viewsets.GenericViewSet):
    """One administrator-only CRM process: campaign, import, Lookup, results, export."""

    authentication_classes = [QualificationAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = Pager
    http_method_names = ['get', 'post', 'head', 'options']

    def campaigns(self):
        return Campaign.objects.filter(portal_workspace=WORKSPACE).order_by('-created_at', '-pk')

    def campaign(self, pk):
        try:
            return self.campaigns().get(pk=pk)
        except (Campaign.DoesNotExist, ValueError, TypeError):
            raise ValidationError('Campagne Isolation introuvable')

    def list(self, request):
        qs = self.campaigns()
        term = request.query_params.get('search', '').strip()[:200]
        if term:
            qs = qs.filter(name__icontains=term)
        return self.get_paginated_response(
            [campaign_output(row) for row in self.paginate_queryset(qs)]
        )

    def create(self, request):
        data = CampaignInput(data=request.data)
        data.is_valid(raise_exception=True)
        campaign = Campaign.objects.create(
            owner=service_owner(),
            portal_workspace=WORKSPACE,
            portal_owner_id=request.user.pk,
            name=data.validated_data['name'],
            purpose=data.validated_data.get('purpose', ''),
            source=data.validated_data.get('source', ''),
            budget=data.validated_data.get('budget', 0),
        )
        audit(request, 'isolation.qualification.campaign_created', campaign)
        return Response(campaign_output(campaign), status=201)

    @action(detail=True, methods=['post'])
    def lookup(self, request, pk=None):
        force = request.data.get('force', False)
        if not isinstance(force, bool):
            raise ValidationError('force doit être un booléen')
        campaign = self.campaign(pk)
        try:
            result = schedule_lookup(campaign, force)
        except ValueError as error:
            raise ValidationError(str(error))
        audit(request, 'isolation.qualification.lookup_scheduled', campaign, **result)
        return Response(result, status=202)

    @action(detail=False, methods=['get', 'post'], url_path='imports')
    def import_file(self, request):
        if request.method == 'GET':
            return self.imports(request)
        campaign = self.campaign(request.data.get('campaign'))
        if campaign.status == 'archived':
            raise ValidationError('Campagne archivée')
        upload = request.FILES.get('file')
        if (
            not upload
            or not upload.name.lower().endswith(('.csv', '.xlsx'))
            or upload.size > settings.MAX_IMPORT_BYTES
        ):
            raise ValidationError('Fichier CSV/XLSX requis, maximum 20 Mo')
        batch = ImportBatch.objects.create(
            campaign=campaign, original=upload, sheet=request.data.get('sheet', '')
        )
        try:
            headers, rows, sheets = read_table(batch)
        except Exception:
            batch.original.delete(save=False)
            batch.delete()
            raise ValidationError('Fichier vide, corrompu ou structure invalide')
        audit(request, 'isolation.qualification.import_uploaded', batch, campaign_id=campaign.pk)
        return Response(
            {
                'id': batch.pk,
                'campaign': campaign.pk,
                'headers': headers,
                'preview': rows[:10],
                'rows': len(rows),
                'sheets': sheets,
            },
            status=201,
        )

    def batch(self, pk):
        try:
            return ImportBatch.objects.select_related('campaign').get(
                pk=pk, campaign__portal_workspace=WORKSPACE
            )
        except (ImportBatch.DoesNotExist, ValueError, TypeError):
            raise ValidationError('Import Isolation introuvable')

    @action(detail=False, methods=['post'], url_path=r'imports/(?P<batch_pk>[^/.]+)/preview')
    def import_preview(self, request, batch_pk=None):
        batch = self.batch(batch_pk)
        if batch.status != 'preview':
            raise ValidationError('Import déjà confirmé')
        batch.sheet = request.data.get('sheet', '')
        try:
            headers, rows, sheets = read_table(batch)
        except (ValueError, KeyError):
            raise ValidationError('Feuille inconnue ou fichier indisponible')
        batch.save(update_fields=['sheet'])
        return Response(
            {
                'id': batch.pk,
                'headers': headers,
                'preview': rows[:10],
                'rows': len(rows),
                'sheets': sheets,
                'sheet': batch.sheet,
            }
        )

    @action(detail=False, methods=['post'], url_path=r'imports/(?P<batch_pk>[^/.]+)/confirm')
    def import_confirm(self, request, batch_pk=None):
        with transaction.atomic():
            batch = (
                ImportBatch.objects.select_for_update()
                .select_related('campaign')
                .get(pk=self.batch(batch_pk).pk, campaign__portal_workspace=WORKSPACE)
            )
            if batch.status != 'preview':
                raise ValidationError('Import déjà confirmé')
            mapping = request.data.get('mapping', {})
            headers, _, _ = read_table(batch)
            if (
                not isinstance(mapping, dict)
                or set(mapping) - {'phone', 'name', 'reference'}
                or mapping.get('phone') not in headers
                or any(value not in headers for value in mapping.values())
            ):
                raise ValidationError('Mappage invalide ; téléphone obligatoire')
            batch.mapping = mapping
            batch.status = 'queued'
            batch.save(update_fields=['mapping', 'status'])
            enqueue('import', batch.pk)
        audit(
            request,
            'isolation.qualification.import_confirmed',
            batch,
            campaign_id=batch.campaign_id,
        )
        return Response({'id': batch.pk, 'status': 'queued'}, status=202)

    def imports(self, request):
        qs = ImportBatch.objects.filter(campaign__portal_workspace=WORKSPACE).order_by(
            '-created_at'
        )
        campaign = request.query_params.get('campaign')
        if campaign:
            qs = qs.filter(campaign_id=campaign)
        return self.get_paginated_response(
            ImportSerializer(self.paginate_queryset(qs), many=True).data
        )

    @action(detail=False, methods=['get'], url_path='results')
    def results(self, request):
        qs = (
            Prospect.objects.select_related('phone', 'campaign')
            .filter(campaign__portal_workspace=WORKSPACE)
            .order_by('-pk')
        )
        campaign = request.query_params.get('campaign')
        if campaign:
            qs = qs.filter(campaign_id=campaign)
        line = request.query_params.get('line_status')
        if line:
            qs = qs.filter(phone__line_status=line)
        term = request.query_params.get('search', '').strip()[:200]
        if term:
            from django.db.models import Q

            qs = qs.filter(
                Q(name__icontains=term)
                | Q(raw_phone__icontains=term)
                | Q(reference__icontains=term)
            )
        return self.get_paginated_response(
            ProspectSerializer(self.paginate_queryset(qs), many=True).data
        )

    def request_export(self, request):
        campaign = self.campaign(request.data.get('campaign'))
        format_name = request.data.get('format', 'xlsx')
        columns = request.data.get('columns', EXPORT_COLUMNS)
        filters = request.data.get('filters', {})
        if (
            format_name not in ('csv', 'xlsx')
            or not isinstance(columns, list)
            or not columns
            or set(columns) - set(EXPORT_COLUMNS)
        ):
            raise ValidationError('Format ou colonnes invalides')
        if (
            not isinstance(filters, dict)
            or set(filters) - FILTERS
            or any(not isinstance(v, str) for v in filters.values())
        ):
            raise ValidationError('Filtres invalides')
        with transaction.atomic():
            job = ExportJob.objects.create(
                campaign=campaign,
                author=service_owner(),
                format=format_name,
                columns=columns,
                filters=filters,
                expires_at=timezone.now() + timedelta(hours=24),
            )
            enqueue('export', job.pk)
        audit(
            request,
            'isolation.qualification.export_requested',
            job,
            campaign_id=campaign.pk,
            format=format_name,
        )
        return Response(ExportSerializer(job).data, status=202)

    @action(detail=False, methods=['get', 'post'], url_path='exports')
    def exports(self, request):
        if request.method == 'POST':
            return self.request_export(request)
        qs = ExportJob.objects.filter(campaign__portal_workspace=WORKSPACE).order_by('-pk')
        return self.get_paginated_response(
            ExportSerializer(self.paginate_queryset(qs), many=True).data
        )

    @action(detail=False, methods=['get'], url_path=r'exports/(?P<job_pk>[^/.]+)/download')
    def download(self, request, job_pk=None):
        try:
            job = ExportJob.objects.get(pk=job_pk, campaign__portal_workspace=WORKSPACE)
        except (ExportJob.DoesNotExist, ValueError, TypeError):
            raise ValidationError('Export Isolation introuvable')
        if job.status != 'completed' or job.expires_at <= timezone.now():
            raise ValidationError('Export non disponible ou expiré')
        audit(request, 'isolation.qualification.export_downloaded', job)
        return FileResponse(
            job.file.open('rb'),
            as_attachment=True,
            filename=f'qualification-isolation-{job.pk}.{job.format}',
        )
