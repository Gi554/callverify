"""Administrative rate identity proofs; no business prices in the identity database."""

from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from packages.access.isolation_events import issue
from .management_api import require_admin
from .models import Membership


class Input(serializers.Serializer):
    setter_id = serializers.IntegerField(min_value=1)

    def validate(self, data):
        if set(self.initial_data) != set(self.fields):
            raise ValidationError('Setter requis, sans champ supplémentaire.')
        return data


@api_view(['POST'])
def rate_proof(request):
    require_admin(request.user, 'isolation')
    serializer = Input(data=request.data)
    serializer.is_valid(raise_exception=True)
    members = Membership.objects.filter(
        workspace='isolation', active=True, user__is_active=True
    ).select_related('user')
    setter = members.filter(role='setter', user_id=serializer.validated_data['setter_id']).first()
    clients = list(members.filter(role='client')[:2])
    if setter is None or len(clients) != 1:
        raise ValidationError('Un setter actif et le client Isolation unique sont requis.')
    data = {
        'actor': request.user.pk,
        'setter': {'id': setter.user_id, 'name': setter.user.username},
        'client': {'id': clients[0].user_id, 'name': clients[0].user.username},
    }
    return Response(
        {
            'proof': issue('compensation_rate', **data),
            'setter': data['setter'],
            'client': data['client'],
        }
    )
