from rest_framework.decorators import api_view
from packages.audit_journal import journal
from .models import BusinessAudit


@api_view(['GET'])
def events(request, pk=None):
    return journal(request, BusinessAudit.objects.all(), 'assurance', pk)
