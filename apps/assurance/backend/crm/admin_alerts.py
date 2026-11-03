import json
from django.db.models import OuterRef, Subquery
from rest_framework.decorators import api_view
from packages import admin_alerts
from . import models


class Roster:
    """Setters known to Assurance, and the audit line written when an alert is reviewed."""

    @staticmethod
    def roster():
        names = {}
        for model in (models.AdvisorAssignment, models.Appointment):
            latest = (
                model.objects.filter(setter_id=OuterRef('setter_id'))
                .order_by('-pk')
                .values('setter_name')[:1]
            )
            names.update(
                dict(
                    model.objects.values('setter_id')
                    .distinct()
                    .annotate(latest_name=Subquery(latest))
                    .values_list('setter_id', 'latest_name')
                )
            )
        return names

    @staticmethod
    def audit(actor, agent, action, data):
        models.BusinessAudit.objects.create(
            actor_id=actor or agent,
            object_id=agent,
            action='payroll.' + action,
            metadata=json.loads(json.dumps({'setter_id': agent, **data}, default=str)),
        )


class Store:
    Roster = Roster
    Meeting = models.Appointment
    Contact = models.Contact
    Task = models.FollowUpTask
    Review = models.SetterAlertReview
    task_relations = ('contact', 'appointment__contact')
    contact_field = 'contact'
    phone = 'phone'
    result = 'report'
    closed_field = 'sale_concluded'
    target = 'advisor'
    audit_prefix = 'payroll.'
    History = models.PayableHistory
    parent = 'appointment'
    closed_alerts = False

    @staticmethod
    def audit_rows():
        return models.BusinessAudit.objects.all()


@api_view(['GET', 'POST'])
def alerts(request):
    return admin_alerts.center(Store, request)
