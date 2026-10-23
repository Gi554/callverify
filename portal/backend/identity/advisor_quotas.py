"""Prospect quota owed to each Assurance advisor's client, visible to every Assurance member."""

from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from .models import Membership

QUOTA_MAX = 100000


def quota_field():
    return serializers.IntegerField(
        min_value=1, max_value=QUOTA_MAX, required=False, allow_null=True
    )


def check_quota(workspace, role, value):
    if value is not None and (workspace, role) != ('assurance', 'advisor'):
        raise ValidationError({'prospect_quota': 'Quota réservé aux conseillers Assurance'})


@api_view(['GET'])
def quotas(request):
    if (
        not request.user.is_active
        or not Membership.objects.filter(
            user=request.user, workspace='assurance', active=True
        ).exists()
    ):
        raise PermissionDenied('Quotas réservés aux membres de l’espace Assurance')
    rows = (
        Membership.objects.filter(
            workspace='assurance', role='advisor', active=True, user__is_active=True
        )
        .select_related('user')
        .order_by('user__username', 'pk')
    )
    response = Response(
        {
            'results': [
                {'id': row.user_id, 'name': row.user.username, 'quota': row.prospect_quota}
                for row in rows
            ]
        }
    )
    response['Cache-Control'] = 'no-store'
    return response
