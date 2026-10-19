from django.urls import path
from .identity import views
from .identity import management_api
from .identity.passwords import change_password
from .identity.recovery import request_reset,confirm_reset
from .identity.isolation import setters as isolation_setters,visit_proof
from .identity.participants import participants,booking_proof,task_owner_proof

urlpatterns=[path('api/portal/csrf/',views.csrf),path('api/portal/login/',views.sign_in),
    path('api/portal/session/',views.session),path('api/portal/access/<str:workspace>/',views.access)]
urlpatterns += [path('api/portal/workspaces/<str:workspace>/users/',management_api.users),
    path('api/portal/workspaces/<str:workspace>/users/<int:pk>/',management_api.update_access)]
urlpatterns += [path('api/portal/assurance/participants/',participants),path('api/portal/assurance/booking-proof/',booking_proof)]
urlpatterns += [path('api/portal/assurance/task-owner-proof/',task_owner_proof)]
urlpatterns += [path('api/portal/isolation/setters/',isolation_setters)]
urlpatterns += [path('api/portal/isolation/visit-proof/',visit_proof)]
urlpatterns += [path('api/portal/password/change/',change_password)]
urlpatterns += [path('api/portal/password/reset/request/',request_reset),path('api/portal/password/reset/confirm/',confirm_reset)]
