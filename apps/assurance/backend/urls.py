from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .crm.imports import imports
from .crm.assignments import AssignmentViewSet
from .crm.views import ContactViewSet,dashboard
router=DefaultRouter();router.register('assignments',AssignmentViewSet,basename='assurance-assignment');router.register('contacts',ContactViewSet,basename='assurance-contact')
urlpatterns=[path('api/assurance/imports/',imports),path('api/assurance/dashboard/',dashboard),path('api/assurance/',include(router.urls))]
