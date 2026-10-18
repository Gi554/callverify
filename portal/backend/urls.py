from django.urls import path
from .identity import views

urlpatterns=[path('api/portal/csrf/',views.csrf),path('api/portal/login/',views.sign_in),
    path('api/portal/session/',views.session),path('api/portal/access/<str:workspace>/',views.access)]
