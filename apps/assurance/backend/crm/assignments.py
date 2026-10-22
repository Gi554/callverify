"""Business associations belong to Assurance; central roles are attested separately."""

from django.core import signing
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from packages.access.assignments import verify_assignment
from .models import AdvisorAssignment, BusinessAudit
from .leases import Conflict


class AssignmentPagination(PageNumberPagination):
    page_size = 25


class AssignmentInput(serializers.Serializer):
    proof = serializers.CharField(max_length=8192)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Seule une confirmation du portail est acceptée')
        return data


class AssignmentUpdate(serializers.Serializer):
    active = serializers.BooleanField()
    revision = serializers.IntegerField(min_value=0)
    proof = serializers.CharField(max_length=8192, required=False)


def admin(user):
    if user.role != 'administrator':
        raise PermissionDenied('Gestion réservée aux administrateurs Assurance')


def proof_for(data, user):
    try:
        return verify_assignment(data.get('proof', ''), user.pk)
    except (signing.BadSignature, ValueError, TypeError, UnicodeError):
        raise ValidationError(
            'Les rôles doivent être confirmés par le portail. Actualisez la sélection des comptes.'
        )


def output(row, is_admin):
    result = {
        'id': row.pk,
        'advisor': {'id': row.advisor_id, 'name': row.advisor_name},
        'active': row.active,
    }
    if is_admin:
        result.update(
            setter={'id': row.setter_id, 'name': row.setter_name},
            revision=row.revision,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    return result


def record(user, row, action, before=None):
    BusinessAudit.objects.create(
        actor_id=user.pk,
        object_id=row.pk,
        action=action,
        metadata={
            'setter_id': row.setter_id,
            'advisor_id': row.advisor_id,
            'before': before,
            'after': {'active': row.active, 'revision': row.revision},
        },
    )


class AssignmentViewSet(viewsets.GenericViewSet):
    serializer_class = AssignmentInput
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    pagination_class = AssignmentPagination

    def get_queryset(self):
        user = self.request.user
        if user.role == 'advisor':
            raise PermissionDenied('Accès non autorisé')
        qs = AdvisorAssignment.objects.order_by('setter_name', 'advisor_name', 'pk')
        if user.role == 'setter':
            return qs.filter(setter_id=user.pk, active=True)
        admin(user)
        state = self.request.query_params.get('active', '')
        if state not in ('', 'true', 'false'):
            raise ValidationError({'active': 'Filtre invalide'})
        if state:
            qs = qs.filter(active=state == 'true')
        term = self.request.query_params.get('search', '').strip()[:150]
        if term:
            qs = qs.filter(Q(setter_name__icontains=term) | Q(advisor_name__icontains=term))
        return qs

    def list(self, request):
        rows = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(
            [output(row, request.user.role == 'administrator') for row in rows]
        )

    def retrieve(self, request, pk=None):
        return Response(output(self.get_object(), request.user.role == 'administrator'))

    def create(self, request):
        admin(request.user)
        data = AssignmentInput(data=request.data)
        data.is_valid(raise_exception=True)
        claims = proof_for(data.validated_data, request.user)
        try:
            with transaction.atomic():
                row = AdvisorAssignment.objects.create(
                    setter_id=claims['setter']['id'],
                    setter_name=claims['setter']['name'],
                    advisor_id=claims['advisor']['id'],
                    advisor_name=claims['advisor']['name'],
                )
                record(request.user, row, 'assignment.created')
        except IntegrityError:
            if AdvisorAssignment.objects.filter(
                setter_id=claims['setter']['id'], advisor_id=claims['advisor']['id']
            ).exists():
                raise Conflict('Cette association existe déjà. Réactivez-la si nécessaire.')
            raise
        return Response(output(row, True), status=201)

    def partial_update(self, request, pk=None):
        admin(request.user)
        row = self.get_object()
        data = AssignmentUpdate(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        if set(request.data) - set(data.fields):
            raise ValidationError('Seuls l’état et la révision peuvent être modifiés')
        changes = {
            'active': values['active'],
            'revision': row.revision + 1,
            'updated_at': timezone.now(),
        }
        if values['active']:
            claims = proof_for(values, request.user)
            if claims['setter']['id'] != row.setter_id or claims['advisor']['id'] != row.advisor_id:
                raise ValidationError('La confirmation concerne une autre association')
            changes.update(
                setter_name=claims['setter']['name'], advisor_name=claims['advisor']['name']
            )
        before = {'active': row.active, 'revision': row.revision}
        with transaction.atomic():
            if row.revision != values['revision'] or not AdvisorAssignment.objects.filter(
                pk=row.pk, revision=values['revision']
            ).update(**changes):
                raise Conflict('Association modifiée entre-temps. Actualisez la liste.')
            for key, value in changes.items():
                setattr(row, key, value)
            record(request.user, row, 'assignment.updated', before)
        return Response(output(row, True))

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        admin(request.user)
        row = self.get_object()
        qs = BusinessAudit.objects.filter(
            object_id=row.pk, action__startswith='assignment.'
        ).order_by('-pk')
        entries = self.paginate_queryset(qs)
        return self.get_paginated_response(
            [
                {
                    'id': item.pk,
                    'action': item.action,
                    'actor_id': item.actor_id,
                    'created_at': item.created_at,
                    'metadata': item.metadata,
                }
                for item in entries
            ]
        )
