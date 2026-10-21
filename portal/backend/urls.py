from django.urls import path
from .identity import views
from .identity import management_api
from .identity import invitations
from .identity import calendars
from .identity import calendar_sync
from .identity.access_history import history as access_history
from .identity.passwords import change_password
from .identity.session_security import revoke_others
from .identity.recovery import request_reset,confirm_reset
from .identity.isolation import setters as isolation_setters,visit_proof
from .identity.participants import participants,booking_proof,task_owner_proof

urlpatterns=[path('api/portal/csrf/',views.csrf),path('api/portal/login/',views.sign_in),
    path('api/portal/session/',views.session),path('api/portal/access/<str:workspace>/',views.access)]
urlpatterns += [path('api/portal/workspaces/<str:workspace>/users/',management_api.users),
    path('api/portal/workspaces/<str:workspace>/users/<int:pk>/',management_api.update_access)]
urlpatterns += [path('api/portal/workspaces/<str:workspace>/access-history/',access_history)]
urlpatterns += [path('api/portal/assurance/participants/',participants),path('api/portal/assurance/booking-proof/',booking_proof)]
urlpatterns += [path('api/portal/assurance/task-owner-proof/',task_owner_proof)]
urlpatterns += [path('api/portal/isolation/setters/',isolation_setters)]
urlpatterns += [path('api/portal/isolation/visit-proof/',visit_proof)]
urlpatterns += [path('api/portal/password/change/',change_password)]
urlpatterns += [path('api/portal/session/revoke-others/',revoke_others)]
urlpatterns += [path('api/portal/calendar/',calendars.connections),
    path('api/portal/calendar/callback/<str:provider>/',calendars.callback),
    path('api/portal/calendar/<str:workspace>/start/',calendars.start),
    path('api/portal/calendar/<str:workspace>/disconnect/',calendars.disconnect),
    path('api/portal/calendar/<str:workspace>/busy/',calendars.busy)]
urlpatterns += [path('api/portal/calendar/<str:workspace>/sync-config/',calendar_sync.configure),
    path('api/portal/calendar/<str:workspace>/sync/',calendar_sync.synchronization),
    path('api/portal/calendar/<str:workspace>/withdraw/',calendar_sync.withdraw_all)]
urlpatterns += [path('api/portal/password/reset/request/',request_reset),path('api/portal/password/reset/confirm/',confirm_reset)]
urlpatterns += [path('api/portal/workspaces/<str:workspace>/invitations/',invitations.invitations),
    path('api/portal/workspaces/<str:workspace>/invitations/<uuid:pk>/',invitations.invitation_action),
    path('api/portal/invitations/accept/',invitations.accept)]

urlpatterns += [path('api/portal/calendar/<str:workspace>/detach/',calendar_sync.detach)]

from .identity.phone_extensions import assignments as phone_assignments
urlpatterns += [path('api/portal/workspaces/<str:workspace>/phone-extensions/',phone_assignments)]

from .identity.phone_directory import directory as phone_directory
urlpatterns += [path('api/portal/phone-directory/',phone_directory)]

from .identity.phone_status import status as phone_status
urlpatterns += [path('api/portal/workspaces/<str:workspace>/phone-extensions/<int:pk>/status/',phone_status)]

from .identity.phone_cdr import schema as phone_cdr_schema
urlpatterns += [path('api/portal/phone-cdr-schema/',phone_cdr_schema)]
from .identity.phone_calls import calls as assurance_calls,status as assurance_call_status
urlpatterns += [path('api/portal/assurance/calls/',assurance_calls),path('api/portal/assurance/calls/<uuid:request_id>/',assurance_call_status)]
urlpatterns += [path('api/portal/isolation/calls/',assurance_calls,{'workspace':'isolation'}),path('api/portal/isolation/calls/<uuid:request_id>/',assurance_call_status,{'workspace':'isolation'})]

from .identity import booking_calendars
urlpatterns += [path("api/portal/internal/assurance/calendar-check/",booking_calendars.availability)]

urlpatterns += [path("api/portal/internal/isolation/calendar-check/",booking_calendars.availability,{"workspace":"isolation"})]
