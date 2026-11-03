from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from packages import admin_alerts
import json
from . import models
from .isolation_work import WorkAuthentication


class Roster:
    """Setters known to Isolation, and the audit line written when an alert is reviewed."""

    @staticmethod
    def roster():
        names = dict(models.IsolationSetterRate.objects.values_list('setter_id', 'setter_name'))
        names.update(
            dict(
                models.IsolationVisit.objects.order_by('pk').values_list('setter_id', 'setter_name')
            )
        )
        return names

    @staticmethod
    def audit(actor, agent, action, data):
        models.AuditEvent.objects.create(
            action='isolation.payroll.' + action,
            object_id=str(agent),
            metadata={
                'actor_portal_id': actor,
                'setter_id': agent,
                **json.loads(json.dumps(data, default=str)),
            },
        )


class Store:
    Roster = Roster
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
    History = models.PayableHistory
    parent = 'visit'
    closed_alerts = True

    @staticmethod
    def audit_rows():
        return models.AuditEvent.objects.all()


@api_view(['GET', 'POST'])
@authentication_classes([WorkAuthentication])
@permission_classes([IsAuthenticated])
def alerts(request):
    return admin_alerts.center(Store, request)
