from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .crm.views import ContactViewSet,dashboard
router=DefaultRouter();router.register('contacts',ContactViewSet,basename='assurance-contact')
urlpatterns=[path('api/assurance/dashboard/',dashboard),path('api/assurance/',include(router.urls))]
