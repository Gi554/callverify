from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from packages import admin_alerts
from . import models
from .payroll import Store as Payroll
from .isolation_work import WorkAuthentication


class Store:
    Payroll = Payroll
    Meeting = models.IsolationVisit
    Contact = models.Prospect
    Task = models.IsolationFollowUp
    Review = models.IsolationAlertReview
    task_relations = ('prospect',)
    contact_field = 'prospect'
    phone = 'raw_phone'
    result = 'result'
    closed_field = 'closed'
    target = 'client'
    audit_prefix = 'isolation.payroll.'

    @staticmethod
    def audit_rows():
        return models.AuditEvent.objects.all()


@api_view(['GET', 'POST'])
@authentication_classes([WorkAuthentication])
@permission_classes([IsAuthenticated])
def alerts(request):
    return admin_alerts.center(Store, request)
