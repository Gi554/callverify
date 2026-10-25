"""Scoped central-identity work queue. Legacy admin APIs keep their own guard."""

from dataclasses import dataclass
from django.core import signing
from django.db import transaction
from django.db.models import F, Q
from rest_framework import serializers, viewsets
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.exceptions import (
    AuthenticationFailed,
    PermissionDenied,
    ValidationError,
    APIException,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from packages.access.tickets import verify
from packages.access.isolation import verify_owner
from .models import Prospect, AuditEvent
from .isolation_activity import ActivityMixin, STATUSES
from .isolation_bulk import BulkAssignmentMixin
from .isolation_lots import LotMixin
from .isolation_phone_calls import IsolationPhoneCallMixin
from .isolation_c2 import C2Mixin
from django.utils import timezone


@dataclass(frozen=True)
class Identity:
    pk: int
    role: str
    is_authenticated: bool = True


class WorkAuthentication(BaseAuthentication):
    roles = ('administrator', 'setter')

    def authenticate_header(self, request):
        return 'Bearer'

    def authenticate(self, request):
        header = get_authorization_header(request).split()
        if not header:
            return None
        if len(header) != 2 or header[0].lower() != b'bearer':
            raise AuthenticationFailed('Jeton Isolation requis')
        try:
            claims = verify(header[1].decode(), 'isolation')
        except (signing.BadSignature, UnicodeDecodeError, ValueError, TypeError):
            raise AuthenticationFailed('Accès Isolation invalide ou expiré')
        if claims['role'] not in self.roles:
            raise PermissionDenied('Rôle non autorisé pour cette ressource Isolation')
        return Identity(int(claims['sub']), claims['role']), claims


class VisitAuthentication(WorkAuthentication):
    roles = ('administrator', 'setter', 'client')


class Conflict(APIException):
    status_code = 409
    default_detail = 'Affectation modifiée : actualisez le prospect'


class ChangeInput(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(max_length=1000)
    proof = serializers.CharField(max_length=3000, required=False)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés')
        return data


class Pager(PageNumberPagination):
    page_size = 25


def visible(user):
    qs = Prospect.objects.select_related('campaign', 'phone')
    return qs if user.role == 'administrator' else qs.filter(assigned_setter_id=user.pk)


def output(row):
    return {
        'id': row.pk,
        'name': row.name,
        'reference': row.reference,
        'raw_phone': row.raw_phone,
        'phone': row.phone.e164 if row.phone_id else None,
        'validity': row.validity,
        'line_status': row.phone.line_status if row.phone_id else 'unknown',
        'campaign': {'id': row.campaign_id, 'name': row.campaign.name},
        'assigned_setter': None
        if row.assigned_setter_id is None
        else {'id': row.assigned_setter_id, 'name': row.assigned_setter_name},
        'revision': row.assignment_revision,
        'commercial_status': row.commercial_status,
        **({'queue_reason': row._queue_reason} if hasattr(row, '_queue_reason') else {}),
        'commercial_label': STATUSES.get(row.commercial_status, row.commercial_status),
        'callback_at': row.callback_at,
        'callback_due': row.callback_at is not None and row.callback_at <= timezone.now(),
    }


from .isolation_followups import FollowUpMixin
from .isolation_export import ExportMixin


class WorkViewSet(
    ExportMixin,
    FollowUpMixin,
    C2Mixin,
    IsolationPhoneCallMixin,
    BulkAssignmentMixin,
    LotMixin,
    ActivityMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = [WorkAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = Pager
    serializer_class = ChangeInput
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        qs = visible(self.request.user).order_by('-pk')
        term = self.request.query_params.get('search', '').strip()[:250]
        if term:
            qs = qs.filter(
                Q(name__icontains=term)
                | Q(raw_phone__icontains=term)
                | Q(reference__icontains=term)
            )
        owner = self.request.query_params.get('owner', '')
        if owner:
            if owner == 'unassigned':
                qs = qs.filter(assigned_setter_id__isnull=True)
            elif owner == 'me':
                qs = qs.filter(assigned_setter_id=self.request.user.pk)
            elif owner.isdigit():
                qs = qs.filter(assigned_setter_id=int(owner))
            else:
                raise ValidationError('Filtre de responsable invalide')
        status = self.request.query_params.get('commercial_status', '')
        if status:
            if status not in STATUSES:
                raise ValidationError('Statut commercial invalide')
            qs = qs.filter(commercial_status=status)
        if self.request.query_params.get('due') == 'true':
            qs = (
                qs.filter(
                    Q(callback_at__lte=timezone.now())
                    | Q(follow_ups__closed_at__isnull=True, follow_ups__due_at__lte=timezone.now())
                )
                .distinct()
                .order_by('callback_at', 'pk')
            )
        mode = self.request.query_params.get('queue', '')
        if mode:
            if mode not in ('active', 'all'):
                raise ValidationError('File de prospection invalide.')
            from django.db.models import Exists, OuterRef, Case, When, Value, CharField
            from .models import IsolationVisit

            qs = qs.annotate(
                _queue_booking=Exists(
                    IsolationVisit.objects.filter(prospect_id=OuterRef('pk'), status='scheduled')
                )
            )
            qs = qs.annotate(
                _queue_reason=Case(
                    When(_queue_booking=True, then=Value('appointment_booked')),
                    When(commercial_status='not_interested', then=Value('not_interested')),
                    default=Value(''),
                    output_field=CharField(),
                )
            )
            if mode == 'active':
                qs = qs.filter(_queue_reason='')
        return qs

    def list(self, request):
        return self.get_paginated_response(
            [output(row) for row in self.paginate_queryset(self.get_queryset())]
        )

    def retrieve(self, request, pk=None):
        return Response(output(self.get_object()))

    def change(self, request, release=False):
        if request.user.role != 'administrator':
            raise PermissionDenied('Affectation réservée aux administrateurs Isolation')
        row = self.get_object()
        serializer = ChangeInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if release:
            if 'proof' in data:
                raise ValidationError('Aucune attestation attendue pour retirer une affectation')
            target_id = None
            target_name = ''
        else:
            try:
                claims = verify_owner(data.get('proof', ''), request.user.pk, row.pk)
            except (signing.BadSignature, TypeError, ValueError):
                raise ValidationError('Attestation de setter invalide ou expirée')
            target_id = claims['setter']
            target_name = claims['name']
        with transaction.atomic():
            if row.assignment_revision != data['revision']:
                raise Conflict()
            if row.assigned_setter_id == target_id:
                raise ValidationError('Affectation déjà identique')
            before = {
                'setter_id': row.assigned_setter_id,
                'setter_name': row.assigned_setter_name,
                'revision': row.assignment_revision,
            }
            if not Prospect.objects.filter(pk=row.pk, assignment_revision=data['revision']).update(
                assigned_setter_id=target_id,
                assigned_setter_name=target_name,
                assignment_revision=F('assignment_revision') + 1,
            ):
                raise Conflict()
            AuditEvent.objects.create(
                action='isolation.prospect.assigned',
                object_id=str(row.pk),
                metadata={
                    'actor_portal_id': request.user.pk,
                    'before': before,
                    'after': {
                        'setter_id': target_id,
                        'setter_name': target_name,
                        'revision': data['revision'] + 1,
                    },
                    'reason': data['reason'],
                },
            )
        row.refresh_from_db()
        return Response(output(row))

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        return self.change(request)

    @action(detail=True, methods=['post'])
    def unassign(self, request, pk=None):
        return self.change(request, release=True)

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        if request.user.role != 'administrator':
            raise PermissionDenied('Historique administratif uniquement')
        row = self.get_object()
        qs = AuditEvent.objects.filter(
            object_id=str(row.pk), action='isolation.prospect.assigned'
        ).order_by('-pk')
        return self.get_paginated_response(
            [
                {'id': e.pk, 'created_at': e.created_at, 'metadata': e.metadata}
                for e in self.paginate_queryset(qs)
            ]
        )


@api_view(['GET'])
@authentication_classes([WorkAuthentication])
@permission_classes([IsAuthenticated])
def dashboard(request):
    qs = visible(request.user)
    return Response(
        {
            'role': request.user.role,
            'prospects': qs.count(),
            'unassigned': qs.filter(assigned_setter_id__isnull=True).count(),
            'callbacks_due': qs.filter(
                Q(callback_at__lte=timezone.now())
                | Q(follow_ups__closed_at__isnull=True, follow_ups__due_at__lte=timezone.now())
            )
            .distinct()
            .count(),
            'open_follow_ups': qs.filter(
                follow_ups__closed_at__isnull=True, follow_ups__isnull=False
            )
            .values('follow_ups')
            .count(),
        }
    )
