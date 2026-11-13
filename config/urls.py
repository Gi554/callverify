from core import isolation_sms
from core.isolation_search import results as admin_search
from core.isolation_performance import own as setter_performance
from core.models import AuditEvent
from packages.support_audit import business_journal_view
from core.isolation_payable import appointments as payable_appointments
from core.isolation_alerts import alerts as admin_alerts
from core.isolation_journal import events as journal_events
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core import views
from core import recovery
from core import settings_api
from core.isolation_work import WorkViewSet, dashboard as workspace_dashboard
from core.isolation_visits import IsolationVisitViewSet
from core.isolation_followups import FollowUps
from core.isolation_client import ClientProspects, client_dashboard
from core.isolation_client_followups import ClientFollowUps
from core.isolation_statistics import statistics as isolation_statistics
from core.isolation_qualification import QualificationViewSet

router = DefaultRouter()
router.register('work-queue', WorkViewSet, basename='isolation-work')
router.register('visits', IsolationVisitViewSet, basename='isolation-visit')
router.register('follow-ups', FollowUps, basename='isolation-follow-up')
router.register('client-prospects', ClientProspects, basename='isolation-client-prospect')
router.register('client-follow-ups', ClientFollowUps, basename='isolation-client-followup')
router.register('qualification', QualificationViewSet, basename='isolation-qualification')
for prefix, view, name in [
    ('campaigns', views.CampaignViewSet, 'campaign'),
    ('imports', views.ImportViewSet, 'import'),
    ('prospects', views.ProspectViewSet, 'prospect'),
    ('lookups', views.LookupViewSet, 'lookup'),
    ('exports', views.ExportViewSet, 'export'),
    ('consents', views.ConsentViewSet, 'consent'),
    ('suppressions', views.SuppressionViewSet, 'suppression'),
    ('calls', views.CallCampaignViewSet, 'call'),
    ('audit', views.AuditViewSet, 'audit'),
]:
    router.register(prefix, view, basename=name)
from core.isolation_notices import Notices

from core.isolation_call_sessions import call_session as isolation_call_session

router.register('isolation-notices', Notices, basename='isolation-notice')
from core.isolation_unqualified import Unqualified

router.register('isolation-unqualified', Unqualified, basename='isolation-unqualified')

urlpatterns = [
    path('api/isolation/call-session/', isolation_call_session),
    path('api/admin-search/', admin_search),
    path('api/setter-performance/', setter_performance),
    path('api/internal/support-journal/', business_journal_view('isolation', AuditEvent)),
    path('api/payable-appointments/', payable_appointments),
    path('api/setter-performance/<int:agent>/', setter_performance),
    path('api/admin-alerts/', admin_alerts),
    path('api/admin-journal/', journal_events),
    path('api/admin-journal/<int:pk>/', journal_events),
    path('api/', include(router.urls)),
    path('api/auth/csrf/', views.csrf),
    path('api/auth/login/', views.login_view),
    path('api/auth/session/', views.session_view),
    path('api/auth/mfa/', views.mfa),
    path('api/administrators/', views.administrators),
    path('api/dashboard/', views.dashboard),
    path('api/webhooks/twilio/voice/', views.voice_webhook),
]
urlpatterns += [
    path('api/auth/reset/request/', recovery.reset_request),
    path('api/auth/reset/confirm/', recovery.reset_confirm),
]
urlpatterns += [
    path('api/settings/', settings_api.platform_settings),
    path('api/notifications/', settings_api.notifications),
    path('api/health/', settings_api.health),
]
urlpatterns += [path('api/webhooks/twilio/amd/', views.voice_webhook)]
urlpatterns += [path('api/workspace-dashboard/', workspace_dashboard)]
urlpatterns += [path('api/client-dashboard/', client_dashboard)]
urlpatterns += [path('api/workspace-statistics/', isolation_statistics)]
from core.client_folders import clients as client_folders, export_client

urlpatterns += [
    path('api/client-folders/', client_folders),
    path('api/client-folders/<int:client_id>/', client_folders),
    path('api/client-folders/<int:client_id>/export/', export_client),
]

from core.isolation_hours import configuration as isolation_hours

urlpatterns += [path('api/isolation-working-hours/', isolation_hours)]

from core.isolation_publication import status as isolation_publication_status

urlpatterns += [path('api/internal/isolation/publication-status/', isolation_publication_status)]

from core import isolation_reminders

urlpatterns += [
    path('api/isolation-reminder-policy/', isolation_reminders.configuration),
    path('api/internal/isolation/sms-visits/', isolation_sms.visits),
    path('api/internal/isolation/mail-events/', isolation_reminders.mail_events),
    path(
        'api/internal/isolation/mail-events/<int:pk>/<int:user_id>/',
        isolation_reminders.mail_eligible,
    ),
]
