from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core import views
from core import recovery
from core import settings_api

router = DefaultRouter()
for prefix, view, name in [('campaigns',views.CampaignViewSet,'campaign'),('imports',views.ImportViewSet,'import'),
    ('prospects',views.ProspectViewSet,'prospect'),('lookups',views.LookupViewSet,'lookup'),
    ('exports',views.ExportViewSet,'export'),('consents',views.ConsentViewSet,'consent'),
    ('suppressions',views.SuppressionViewSet,'suppression'),('calls',views.CallCampaignViewSet,'call'),
    ('audit',views.AuditViewSet,'audit')]:
    router.register(prefix,view,basename=name)
urlpatterns = [path('api/',include(router.urls)), path('api/auth/csrf/',views.csrf),
    path('api/auth/login/',views.login_view),path('api/auth/session/',views.session_view),
    path('api/auth/mfa/',views.mfa),path('api/administrators/',views.administrators),
    path('api/dashboard/',views.dashboard),path('api/webhooks/twilio/voice/',views.voice_webhook)]
urlpatterns += [path('api/auth/reset/request/',recovery.reset_request),path('api/auth/reset/confirm/',recovery.reset_confirm)]
urlpatterns += [path('api/settings/',settings_api.platform_settings),path('api/notifications/',settings_api.notifications),path('api/health/',settings_api.health)]
