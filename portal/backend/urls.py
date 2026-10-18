from django.urls import path
from .identity import views
from .identity import management_api
from .identity.participants import participants,booking_proof

urlpatterns=[path('api/portal/csrf/',views.csrf),path('api/portal/login/',views.sign_in),
    path('api/portal/session/',views.session),path('api/portal/access/<str:workspace>/',views.access)]
urlpatterns += [path('api/portal/workspaces/<str:workspace>/users/',management_api.users),
    path('api/portal/workspaces/<str:workspace>/users/<int:pk>/',management_api.update_access)]
urlpatterns += [path('api/portal/assurance/participants/',participants),path('api/portal/assurance/booking-proof/',booking_proof)]
