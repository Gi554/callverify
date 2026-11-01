from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from packages.audit_journal import journal
from .isolation_work import WorkAuthentication
from .models import AuditEvent


@api_view(['GET'])
@authentication_classes([WorkAuthentication])
@permission_classes([IsAuthenticated])
def events(request, pk=None):
    return journal(
        request, AuditEvent.objects.filter(action__startswith='isolation.'), 'isolation', pk
    )
