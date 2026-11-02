"""Compatibility endpoint for old browser sessions after retirement of the closer role."""

from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from .models import Membership


@api_view(['GET', 'POST'])
def closers(request):
    if not Membership.objects.filter(
        user=request.user,
        workspace='isolation',
        active=True,
        role__in=('administrator', 'client', 'setter'),
    ).exists():
        raise PermissionDenied('Accès Isolation non autorisé.')
    if request.method == 'GET':
        return Response({'count': 0, 'results': [], 'next': None, 'previous': None})
    return Response(
        {
            'detail': 'Le rôle Closer a été supprimé. Le client Isolation assure le suivi des visites.'
        },
        status=410,
    )
