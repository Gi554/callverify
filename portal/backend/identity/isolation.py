from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django.db.models import Q
from .management_api import require_admin
from .models import Membership, AccessAudit
from packages.access.isolation import issue_owner


class AssignmentInput(serializers.Serializer):
    setter_id = serializers.IntegerField(min_value=1)
    prospect_id = serializers.IntegerField(min_value=1)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise ValidationError('Champs non autorisés')
        return data


@api_view(['GET', 'POST'])
def setters(request):
    require_admin(request.user, 'isolation')
    qs = Membership.objects.filter(
        workspace='isolation', role='setter', active=True, user__is_active=True
    ).select_related('user')
    if request.method == 'GET':
        term = request.query_params.get('search', '').strip()[:150]
        if term:
            qs = qs.filter(Q(user__username__icontains=term) | Q(user__email__icontains=term))
        pager = PageNumberPagination()
        pager.page_size = 25
        rows = pager.paginate_queryset(qs.order_by('user__username', 'pk'), request)
        return pager.get_paginated_response(
            [{'id': row.user_id, 'name': row.user.username} for row in rows]
        )
    serializer = AssignmentInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    target = qs.filter(user_id=data['setter_id']).first()
    if target is None:
        raise ValidationError('Setter Isolation actif requis')
    AccessAudit.objects.create(
        user=request.user, workspace='isolation', action='prospect.owner_attested', metadata=data
    )
    return Response(
        {
            'proof': issue_owner(
                request.user.pk, data['prospect_id'], target.user_id, target.user.username
            ),
            'expires_in': 120,
        }
    )


@api_view(['POST'])
def visit_proof(request):
    from packages.access.isolation_visits import issue_booking

    actor = Membership.objects.filter(user=request.user, workspace='isolation', active=True).first()
    if not actor or actor.role not in ('administrator', 'setter'):
        raise PermissionDenied('Réservation Isolation non autorisée')
    serializer = AssignmentInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if actor.role == 'setter' and data['setter_id'] != request.user.pk:
        raise PermissionDenied('Réservation limitée à vos prospects')
    active = Membership.objects.filter(
        workspace='isolation', active=True, user__is_active=True
    ).select_related('user')
    setter = active.filter(role='setter', user_id=data['setter_id']).first()
    clients = list(active.filter(role='client').order_by('pk')[:2])
    if setter is None:
        raise ValidationError('Setter Isolation actif requis')
    if len(clients) != 1:
        raise ValidationError('Configurer exactement un client Isolation actif pour réserver')
    client = clients[0]
    AccessAudit.objects.create(
        user=request.user,
        workspace='isolation',
        action='visit.booking_attested',
        metadata={**data, 'client_id': client.user_id},
    )
    return Response(
        {
            'proof': issue_booking(
                request.user.pk,
                data['prospect_id'],
                setter.user_id,
                setter.user.username,
                client.user_id,
                client.user.username,
            ),
            'expires_in': 120,
        }
    )
