"""Active central participants, only visible to Assurance administrators."""

from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django.db.models import Q
from .models import Membership, AccessAudit
from .management_api import require_admin
from packages.access.assignments import issue_assignment


class PairInput(serializers.Serializer):
    setter_id = serializers.IntegerField(min_value=1)
    advisor_id = serializers.IntegerField(min_value=1)


class TaskOwnerInput(serializers.Serializer):
    task_id = serializers.IntegerField(min_value=1)
    setter_id = serializers.IntegerField(min_value=1)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés')
        return data


@api_view(['POST'])
def task_owner_proof(request):
    from packages.access.followups import issue_owner

    require_admin(request.user, 'assurance')
    serializer = TaskOwnerInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    target = (
        Membership.objects.filter(
            workspace='assurance',
            role='setter',
            active=True,
            user__is_active=True,
            user_id=data['setter_id'],
        )
        .select_related('user')
        .first()
    )
    if target is None:
        raise ValidationError('Setter Assurance actif requis')
    AccessAudit.objects.create(
        user=request.user, action='follow_up.owner_attested', workspace='assurance', metadata=data
    )
    return Response(
        {
            'proof': issue_owner(
                request.user.pk, data['task_id'], target.user_id, target.user.username
            ),
            'expires_in': 120,
        }
    )


class LotInput(serializers.Serializer):
    setter_id = serializers.IntegerField(min_value=1)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés')
        return data


@api_view(['POST'])
def lot_proof(request):
    from packages.access.followups import issue_lot

    require_admin(request.user, 'assurance')
    serializer = LotInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    target = (
        Membership.objects.filter(
            workspace='assurance',
            role__in=('setter', 'administrator'),
            active=True,
            user__is_active=True,
            user_id=data['setter_id'],
        )
        .select_related('user')
        .first()
    )
    if target is None:
        raise ValidationError('Setter ou administrateur Assurance actif requis')
    AccessAudit.objects.create(
        user=request.user, action='lot.setter_attested', workspace='assurance', metadata=data
    )
    return Response(
        {
            'proof': issue_lot(request.user.pk, target.user_id, target.user.username),
            'expires_in': 120,
        }
    )


@api_view(['GET', 'POST'])
def participants(request):
    require_admin(request.user, 'assurance')
    active = Membership.objects.filter(
        workspace='assurance', active=True, user__is_active=True
    ).select_related('user')
    if request.method == 'GET':
        role = request.query_params.get('role', '')
        if role not in ('setter', 'advisor', 'administrator'):
            raise ValidationError({'role': 'Choisir setter, advisor ou administrator'})
        qs = active.filter(role=role).order_by('user__username', 'pk')
        term = request.query_params.get('search', '').strip()[:150]
        if term:
            qs = qs.filter(Q(user__username__icontains=term) | Q(user__email__icontains=term))
        pager = PageNumberPagination()
        pager.page_size = 25
        rows = pager.paginate_queryset(qs, request)
        return pager.get_paginated_response(
            [{'id': row.user_id, 'name': row.user.username, 'role': row.role} for row in rows]
        )
    data = PairInput(data=request.data)
    data.is_valid(raise_exception=True)
    pair = {
        role: active.filter(role=role, user_id=data.validated_data[role + '_id']).first()
        for role in ('setter', 'advisor')
    }
    if not all(pair.values()):
        raise ValidationError(
            'Sélection indisponible : les deux comptes doivent être actifs avec le rôle Assurance attendu'
        )
    setter, advisor = pair['setter'], pair['advisor']
    AccessAudit.objects.create(
        user=request.user,
        action='assignment.attested',
        workspace='assurance',
        metadata={'setter_id': setter.user_id, 'advisor_id': advisor.user_id},
    )
    return Response(
        {
            'proof': issue_assignment(
                request.user.pk,
                setter.user_id,
                setter.user.username,
                advisor.user_id,
                advisor.user.username,
            ),
            'expires_in': 120,
        }
    )


@api_view(['POST'])
def booking_proof(request):
    from rest_framework.exceptions import PermissionDenied
    from packages.access.assignments import issue_booking

    actor = Membership.objects.filter(user=request.user, workspace='assurance', active=True).first()
    if not actor or actor.role not in ('setter', 'administrator'):
        raise PermissionDenied('Réservation non autorisée')
    submitted = request.data.copy()
    if actor.role == 'setter' and 'setter_id' not in submitted:
        submitted['setter_id'] = request.user.pk
    data = PairInput(data=submitted)
    data.is_valid(raise_exception=True)
    values = data.validated_data
    if actor.role == 'setter' and values['setter_id'] != request.user.pk:
        raise PermissionDenied('Réservation limitée à vos propres attributions')
    active = Membership.objects.filter(
        workspace='assurance', active=True, user__is_active=True
    ).select_related('user')
    pair = {
        role: active.filter(role=role, user_id=values[role + '_id']).first()
        for role in ('setter', 'advisor')
    }
    if not all(pair.values()):
        raise ValidationError('Comptes indisponibles pour une réservation Assurance')
    setter, advisor = pair['setter'], pair['advisor']
    AccessAudit.objects.create(
        user=request.user, action='booking.attested', workspace='assurance', metadata=values
    )
    return Response(
        {
            'proof': issue_booking(
                request.user.pk,
                setter.user_id,
                setter.user.username,
                advisor.user_id,
                advisor.user.username,
            ),
            'expires_in': 120,
        }
    )
