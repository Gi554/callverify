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
        # Names are snapshots on rates/visits.  Never let an empty or whitespace
        # snapshot overwrite a real name from another record: doing so made the
        # admin performance selector fall back to technical labels such as
        # ``Setter #18`` and ``Setter #25``.
        names = {}
        for setter_id, setter_name in models.IsolationSetterRate.objects.order_by('pk').values_list(
            'setter_id', 'setter_name'
        ):
            clean = (setter_name or '').strip()
            if clean:
                names[setter_id] = clean
        for setter_id, setter_name in models.IsolationVisit.objects.order_by('pk').values_list(
            'setter_id', 'setter_name'
        ):
            clean = (setter_name or '').strip()
            if clean:
                names[setter_id] = clean
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
