from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .crm.imports import imports
from .crm.custom_fields import definitions
from .crm.pipeline import configuration
from .crm.statistics import statistics
from .crm.policies import follow_up_policy, policy_history
from .crm.reports import FollowUpViewSet
from .crm.notifications import TaskNotificationViewSet
from .crm.mail_bridge import events as mail_events, eligible as mail_eligible
from .crm.reminders import reminders, configuration as reminder_configuration
from .crm.mail_bridge import reminder_events, reminder_eligible
from .crm.mail_bridge import escalation_events, escalation_eligible
from .crm.assignments import AssignmentViewSet
from .crm.appointments import AppointmentViewSet
from .crm import calendly
from .crm.booking_links import own as own_booking_link
from .crm.appointment_notifications import AppointmentNotificationViewSet
from .crm.views import ContactViewSet, dashboard
from .crm.lots import lots, release as lots_release

router = DefaultRouter()
router.register(
    'appointment-notifications',
    AppointmentNotificationViewSet,
    basename='assurance-appointment-notification',
)
router.register('follow-ups', FollowUpViewSet, basename='assurance-follow-up')
router.register('appointments', AppointmentViewSet, basename='assurance-appointment')
router.register('assignments', AssignmentViewSet, basename='assurance-assignment')
router.register('contacts', ContactViewSet, basename='assurance-contact')
router.register('notifications', TaskNotificationViewSet, basename='assurance-notification')
urlpatterns = [path('api/assurance/pipeline/', configuration)]
urlpatterns += [path('api/assurance/advisor-booking-link/', own_booking_link)]
urlpatterns += [path('api/assurance/internal/calendly/', calendly.internal)]
urlpatterns += [path('api/assurance/calendly/pending/', calendly.pending)]
urlpatterns += [
    path('api/assurance/calendly/slots/', calendly.slots),
    path('api/assurance/calendly/book/', calendly.book),
]
urlpatterns += [
    path('api/assurance/reminders/', reminders),
    path('api/assurance/reminder-policy/', reminder_configuration),
]
urlpatterns += [
    path('api/assurance/internal/reminder-mail-events/', reminder_events),
    path('api/assurance/internal/reminder-mail-events/<int:pk>/<int:user_id>/', reminder_eligible),
]
urlpatterns += [
    path('api/assurance/internal/escalation-mail-events/', escalation_events),
    path(
        'api/assurance/internal/escalation-mail-events/<int:pk>/<int:user_id>/', escalation_eligible
    ),
]
urlpatterns += [
    path('api/assurance/internal/mail-events/', mail_events),
    path('api/assurance/internal/mail-events/<int:pk>/<int:user_id>/', mail_eligible),
]
urlpatterns += [
    path('api/assurance/contact-fields/', definitions),
    path('api/assurance/statistics/', statistics),
    path('api/assurance/follow-up-policy/', follow_up_policy),
    path('api/assurance/follow-up-policy/history/', policy_history),
    path('api/assurance/imports/', imports),
    path('api/assurance/lots/', lots),
    path('api/assurance/lots/release/', lots_release),
    path('api/assurance/dashboard/', dashboard),
    path('api/assurance/', include(router.urls)),
]

from .crm.agreement_registry import registry as agreement_registry

urlpatterns += [path('api/assurance/agreement-registry/', agreement_registry)]
from .crm.agreement_export import export as agreement_export

urlpatterns += [path('api/assurance/agreement-registry/export/', agreement_export)]

from .crm.agreement_registry import deadlines as agreement_deadlines

urlpatterns += [path('api/assurance/agreement-deadlines/', agreement_deadlines)]

from .crm.advisor_usage import usage as advisor_usage, prospects as advisor_prospects

urlpatterns += [path('api/assurance/advisor-usage/', advisor_usage)]
urlpatterns += [path('api/assurance/advisor-prospects/', advisor_prospects)]
from .crm.advisor_availability import availability as advisor_availability

urlpatterns += [path('api/assurance/advisor-availability/', advisor_availability)]
from .crm.client_folders import clients as client_folders, export_client

urlpatterns += [
    path('api/assurance/client-folders/', client_folders),
    path('api/assurance/client-folders/<int:client_id>/', client_folders),
    path('api/assurance/client-folders/<int:client_id>/export/', export_client),
]
