from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .crm.imports import imports
from .crm.custom_fields import definitions
from .crm.pipeline import configuration
from .crm.statistics import statistics
from .crm.policies import follow_up_policy,policy_history
from .crm.reports import FollowUpViewSet
from .crm.notifications import TaskNotificationViewSet
from .crm.mail_bridge import events as mail_events,eligible as mail_eligible
from .crm.assignments import AssignmentViewSet
from .crm.appointments import AppointmentViewSet
from .crm.views import ContactViewSet,dashboard
router=DefaultRouter();router.register('follow-ups',FollowUpViewSet,basename='assurance-follow-up');router.register('appointments',AppointmentViewSet,basename='assurance-appointment');router.register('assignments',AssignmentViewSet,basename='assurance-assignment');router.register('contacts',ContactViewSet,basename='assurance-contact')
router.register('notifications',TaskNotificationViewSet,basename='assurance-notification')
urlpatterns=[path('api/assurance/pipeline/',configuration)]
urlpatterns += [path('api/assurance/internal/mail-events/',mail_events),path('api/assurance/internal/mail-events/<int:pk>/<int:user_id>/',mail_eligible)]
urlpatterns += [path('api/assurance/contact-fields/',definitions),path('api/assurance/statistics/',statistics),path('api/assurance/follow-up-policy/',follow_up_policy),path('api/assurance/follow-up-policy/history/',policy_history),path('api/assurance/imports/',imports),path('api/assurance/dashboard/',dashboard),path('api/assurance/',include(router.urls))]
