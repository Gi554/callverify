from rest_framework.decorators import api_view
from packages import admin_alerts
from . import models
from .payroll import Store as Payroll


class Store:
    Payroll = Payroll
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

    @staticmethod
    def audit_rows():
        return models.BusinessAudit.objects.all()


@api_view(['GET', 'POST'])
def alerts(request):
    return admin_alerts.center(Store, request)
