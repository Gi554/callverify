from django.db.models import F, Q
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from .models import AppointmentNotification

LABELS = {
    'appointment_transmitted': 'Nouveau rendez-vous transmis',
    'attendance_confirmed': 'Rendez-vous validé',
    'attendance_absent': 'Rendez-vous non honoré',
}


class Pager(PageNumberPagination):
    page_size = 25


class AppointmentNotificationViewSet(viewsets.GenericViewSet):
    pagination_class = Pager
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        if user.role not in ('advisor', 'setter', 'administrator'):
            raise PermissionDenied('Espace Assurance requis.')
        return (
            AppointmentNotification.objects.filter(
                recipient_id=user.pk, role=user.role, appointment__status='scheduled'
            )
            .filter(
                Q(role='advisor', appointment__advisor_id=F('recipient_id'))
                | Q(role='setter', appointment__setter_id=F('recipient_id'))
            )
            .select_related('appointment__contact')
            .order_by('-created_at', '-pk')
        )

    def list(self, request):
        rows = self.paginate_queryset(self.get_queryset())
        response = self.get_paginated_response(
            [
                {
                    'id': row.pk,
                    'appointment_id': row.appointment_id,
                    'contact_name': row.appointment.contact.name,
                    'starts_at': row.appointment.starts_at,
                    'meeting_type': row.appointment.meeting_type,
                    'label': LABELS.get(row.kind, row.kind),
                    'read_at': row.read_at,
                    'created_at': row.created_at,
                }
                for row in rows
            ]
        )
        response['Cache-Control'] = 'no-store'
        return response

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        row = self.get_object()
        AppointmentNotification.objects.filter(pk=row.pk, read_at__isnull=True).update(
            read_at=timezone.now()
        )
        return Response({'read': True})
