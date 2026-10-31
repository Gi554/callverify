from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core import views
from core import recovery
from core import settings_api
from core.isolation_work import WorkViewSet, dashboard as workspace_dashboard
from core.isolation_visits import IsolationVisitViewSet
from core.isolation_closers import CloserVisits
from core.isolation_followups import FollowUps
from core.isolation_client import ClientProspects, client_dashboard
from core.isolation_statistics import statistics as isolation_statistics
from core.isolation_qualification import QualificationViewSet

router = DefaultRouter()
router.register('work-queue', WorkViewSet, basename='isolation-work')
router.register('visits', IsolationVisitViewSet, basename='isolation-visit')
router.register('closer-visits', CloserVisits, basename='isolation-closer-visit')
router.register('follow-ups', FollowUps, basename='isolation-follow-up')
router.register('client-prospects', ClientProspects, basename='isolation-client-prospect')
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
urlpatterns = [
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
