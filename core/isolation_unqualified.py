"""Explicitly share interested, not-yet-programmable prospects with the unique client."""

from django.db import transaction
from django.db.models import Q, Value
from django.db.models.functions import Replace
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .isolation_work import VisitAuthentication, Pager, Conflict, visible
from .isolation_visits import proof, lock_prospect
from .isolation_c2 import defaults, C2Input, DraftInput
from .isolation_followups import event, fingerprint
from .isolation_activity import output as activity_output
from .models import IsolationUnqualified, IsolationVisit, ProspectActivity, AuditEvent

REASONS = {
    'out_of_area': 'Hors zone d’intervention',
    'city_not_served': 'Ville non desservie actuellement',
    'distance': 'Distance trop importante',
    'other': 'Autre',
}


class Input(serializers.Serializer):
    prospect_id = serializers.IntegerField(min_value=1)
    request_id = serializers.UUIDField()
    revision = serializers.IntegerField(min_value=0)
    proof = serializers.CharField(max_length=3000)
    reason = serializers.ChoiceField(choices=list(REASONS))
    note = serializers.CharField(max_length=3000, allow_blank=True, default='')

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés.')
        return data


def output(row):
    return {
        'id': row.pk,
        'prospect_id': row.prospect_id,
        'name': row.qualification.get('full_name') or row.prospect.name,
        'phone': row.qualification.get('phone') or row.prospect.raw_phone,
        'city': row.city,
        'postal_code': row.postal_code,
        'reason': row.reason,
        'reason_label': REASONS[row.reason],
        'note': row.note,
        'qualification': {
            'version': 1,
            'fields': row.qualification,
            'captured_at': row.created_at.isoformat(),
            'campaign_id': row.prospect.campaign_id,
        },
        'setter': {'id': row.setter_id, 'name': row.setter_name},
        'client': {'id': row.client_id, 'name': row.client_name},
        'created_at': row.created_at,
        'active': row.active,
        'programmed_visit_id': row.programmed_visit_id,
    }


class Unqualified(viewsets.GenericViewSet):
    authentication_classes = [VisitAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = Pager
    serializer_class = Input
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        rows = IsolationUnqualified.objects.select_related('prospect')
        if user.role == 'client':
            rows = rows.filter(client_id=user.pk)
        elif user.role == 'setter':
            rows = rows.filter(prospect__assigned_setter_id=user.pk)
        if self.action != 'list':
            return rows
        rows = rows.filter(active=True)
        for field in ('city', 'reason'):
            term = self.request.query_params.get(field, '').strip()
            if len(term) > 150 or (field == 'reason' and term and term not in REASONS):
                raise ValidationError('Filtre invalide.')
            if term:
                rows = rows.filter(**{field + ('__icontains' if field == 'city' else ''): term})
        postal = ''.join(self.request.query_params.get('postal_code', '').split()).upper()
        if len(postal) > 10:
            raise ValidationError('Code postal invalide.')
        if postal:
            rows = rows.annotate(_postal=Replace('postal_code', Value(' '), Value(''))).filter(
                _postal__icontains=postal
            )
        term = self.request.query_params.get('search', '').strip()[:250]
        if term:
            rows = rows.filter(
                Q(prospect__name__icontains=term) | Q(prospect__raw_phone__icontains=term)
            )
        ordering = {
            'date': ('created_at', 'pk'),
            '-date': ('-created_at', '-pk'),
            'setter': ('setter_name', '-pk'),
        }
        sort = self.request.query_params.get('sort', '-date')
        if sort not in ordering:
            raise ValidationError('Tri invalide.')
        return rows.order_by(*ordering[sort])

    def list(self, request):
        response = self.get_paginated_response(
            [output(row) for row in self.paginate_queryset(self.get_queryset())]
        )
        response['Cache-Control'] = 'no-store'
        return response

    def retrieve(self, request, pk=None):
        response = Response(output(self.get_object()))
        response['Cache-Control'] = 'no-store'
        return response

    def requalification_entry(self):
        if self.request.user.role != 'client':
            raise PermissionDenied('Requalification directe réservée au client de la fiche.')
        row = self.get_object()
        if not row.active:
            raise Conflict('Cette fiche a déjà été programmée.')
        return row

    @action(detail=True, methods=['get'])
    def prospect(self, request, pk=None):
        row = self.requalification_entry().prospect
        response = Response(
            {
                'id': row.pk,
                'name': row.name,
                'raw_phone': row.raw_phone,
                'revision': row.assignment_revision,
                'assigned_setter': None
                if row.assigned_setter_id is None
                else {'id': row.assigned_setter_id, 'name': row.assigned_setter_name},
            }
        )
        response['Cache-Control'] = 'no-store'
        return response

    @action(detail=True, methods=['get', 'post'])
    def qualification(self, request, pk=None):
        entry = self.requalification_entry()
        prospect = entry.prospect
        if request.method == 'POST':
            serializer = DraftInput(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            with transaction.atomic():
                prospect = lock_prospect(prospect, request.user, data['revision'])
                if not IsolationUnqualified.objects.filter(
                    pk=entry.pk, active=True, client_id=request.user.pk
                ).exists():
                    raise Conflict('Cette fiche a déjà été programmée.')
                before = prospect.c2
                prospect.c2 = data['c2']
                prospect.save(update_fields=['c2'])
                AuditEvent.objects.create(
                    action='isolation.unqualified.qualification_saved',
                    object_id=str(entry.pk),
                    metadata={
                        'actor_portal_id': request.user.pk,
                        'prospect_id': prospect.pk,
                        'before': before,
                        'after': prospect.c2,
                        'revision': prospect.assignment_revision,
                    },
                )
        response = Response(
            {
                'c2': prospect.c2,
                'defaults': defaults(prospect),
                'revision': prospect.assignment_revision,
            }
        )
        response['Cache-Control'] = 'no-store'
        return response

    def create(self, request):
        if request.user.role not in ('setter', 'administrator'):
            raise PermissionDenied('Enregistrement réservé au setter et à l’administration.')
        serializer = Input(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        prospect = get_object_or_404(visible(request.user), pk=data['prospect_id'])
        claims = proof(data, request.user, prospect)
        digest = fingerprint(
            {key: data[key] for key in ('prospect_id', 'reason', 'note')}
            | {'client': claims['client']['id'], 'setter': claims['setter']['id']}
        )

        def replay(row):
            if row.actor_id != request.user.pk or row.fingerprint != digest:
                raise Conflict('Identifiant déjà utilisé pour une autre demande.')
            return Response(output(row))

        existing = (
            IsolationUnqualified.objects.filter(request_id=data['request_id'])
            .select_related('prospect')
            .first()
        )
        if existing:
            return replay(existing)
        with transaction.atomic():
            try:
                prospect = lock_prospect(prospect, request.user, data['revision'])
            except Conflict:
                existing = (
                    IsolationUnqualified.objects.filter(request_id=data['request_id'])
                    .select_related('prospect')
                    .first()
                )
                if existing:
                    return replay(existing)
                raise
            if prospect.assigned_setter_id != claims['setter']['id']:
                raise Conflict('Responsable modifié : rechargez.')
            if IsolationUnqualified.objects.filter(prospect=prospect, active=True).exists():
                raise Conflict('Cette fiche est déjà dans les rendez-vous non qualifiés.')
            if IsolationVisit.objects.filter(
                prospect=prospect, status='scheduled', ends_at__gt=timezone.now()
            ).exists():
                raise Conflict('Une visite est déjà programmée pour ce prospect.')
            known = C2Input(data=prospect.c2)
            known.is_valid(raise_exception=True)
            fields = dict(known.validated_data)
            fields.update(
                {key: value for key, value in defaults(prospect).items() if key not in prospect.c2}
            )
            row = IsolationUnqualified.objects.create(
                prospect=prospect,
                client_id=claims['client']['id'],
                client_name=claims['client']['name'],
                setter_id=claims['setter']['id'],
                setter_name=claims['setter']['name'],
                actor_id=request.user.pk,
                request_id=data['request_id'],
                fingerprint=digest,
                reason=data['reason'],
                note=data['note'],
                qualification=fields,
                city=fields['city'],
                postal_code=fields['postal_code'],
            )
            event(
                prospect,
                request.user,
                'unqualified',
                data['note'],
                {'reason': data['reason'], 'unqualified_id': row.pk, 'client_id': row.client_id},
            )
            AuditEvent.objects.create(
                action='isolation.unqualified.created',
                object_id=str(row.pk),
                metadata={
                    'actor_portal_id': request.user.pk,
                    'prospect_id': prospect.pk,
                    'client_id': row.client_id,
                    'setter_id': row.setter_id,
                    'reason': row.reason,
                },
            )
        return Response(output(row), status=201)

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        row = self.get_object()
        rows = ProspectActivity.objects.filter(prospect_id=row.prospect_id).order_by('-pk')
        response = self.get_paginated_response(
            [activity_output(event) for event in self.paginate_queryset(rows)]
        )
        response['Cache-Control'] = 'no-store'
        return response

    @action(detail=True, methods=['get'])
    def callbacks(self, request, pk=None):
        row = self.get_object()
        rows = row.prospect.follow_ups.order_by('-pk')
        response = self.get_paginated_response(
            [
                {
                    'id': task.pk,
                    'due_at': task.due_at,
                    'note': task.note,
                    'closed_at': task.closed_at,
                    'resolution': task.resolution,
                }
                for task in self.paginate_queryset(rows)
            ]
        )
        response['Cache-Control'] = 'no-store'
        return response
