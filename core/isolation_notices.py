"""Private in-app visit notices; reading never changes attendance or tasks."""

import hashlib
from datetime import timedelta
from uuid import uuid4
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .isolation_work import WorkAuthentication, Pager
from .models import IsolationNotice, IsolationFollowUp, AuditEvent


class NoticeAuthentication(WorkAuthentication):
    roles = ('setter', 'administrator', 'client', 'closer')


def notice(visit, recipient, role, kind, key):
    if recipient:
        IsolationNotice.objects.get_or_create(
            event_key=key,
            defaults={
                'visit': visit,
                'recipient_id': recipient,
                'recipient_role': role,
                'kind': kind,
                'anchor_at': visit.starts_at,
            },
        )


def result_changed(visit, report, previous, actor):
    from .isolation_followups import sync

    # Task ownership follows the prospect's current setter, as for existing manual callbacks.
    prospect = visit.prospect
    owner = prospect.assigned_setter_id
    if not report.performed:
        task, created = IsolationFollowUp.objects.get_or_create(
            absence_visit=visit,
            defaults={
                'prospect': prospect,
                'request_id': uuid4(),
                'created_by_id': None,
                'fingerprint': hashlib.sha256(f'absence:{visit.pk}'.encode()).hexdigest(),
                'note': 'Visite non tenue : rappeler le prospect pour programmer une nouvelle visite.',
                'due_at': timezone.now() + timedelta(hours=24),
            },
        )
        if not created and task.closed_at and previous and previous.get('performed'):
            before = {
                'closed_at': task.closed_at.isoformat(),
                'resolution': task.resolution,
                'revision': task.revision,
            }
            task.closed_at = None
            task.closed_by_id = None
            task.resolution = ''
            task.due_at = timezone.now() + timedelta(hours=24)
            task.revision += 1
            task.save(
                update_fields=['closed_at', 'closed_by_id', 'resolution', 'due_at', 'revision']
            )
            AuditEvent.objects.create(
                action='isolation.callback.absence_reopened',
                object_id=str(task.pk),
                metadata={'actor_portal_id': actor.pk, 'visit_id': visit.pk, 'before': before},
            )
        sync(prospect)
    if (
        previous
        and previous['performed'] == report.performed
        and previous.get('closed') == report.closed
    ):
        return
    kind = 'closed' if report.closed else 'held' if report.performed else 'not_held'
    notice(visit, owner, 'setter', kind, f'result:{visit.pk}:{visit.revision}')


class Notices(viewsets.GenericViewSet):
    authentication_classes = [NoticeAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = Pager

    def get_queryset(self):
        from django.db.models import Q
        from .isolation_reminders import candidates

        rows = IsolationNotice.objects.filter(
            recipient_id=self.request.user.pk, recipient_role=self.request.user.role
        )
        rows = rows.filter(
            ~Q(kind__in=['booked', 'result_due']) | Q(pk__in=candidates().values('pk'))
        )
        if self.request.query_params.get('unread') == 'true':
            rows = rows.filter(read_at__isnull=True)
        return rows.select_related('visit__prospect').order_by('-pk')

    def list(self, request):
        rows = self.paginate_queryset(self.get_queryset())
        labels = {
            'held': 'Visite tenue',
            'not_held': 'Visite non tenue : rappel à effectuer',
            'closed': 'Vente conclue',
            'booked': 'Nouvelle visite programmée',
            'result_due': 'Résultat de visite à renseigner',
        }
        response = self.get_paginated_response(
            [
                {
                    'id': r.pk,
                    'visit_id': r.visit_id,
                    'prospect_id': r.visit.prospect_id,
                    'prospect_name': r.visit.prospect.name,
                    'kind': r.kind,
                    'label': labels.get(r.kind, r.kind),
                    'created_at': r.created_at,
                    'read_at': r.read_at,
                    'starts_at': r.visit.starts_at,
                }
                for r in rows
            ]
        )
        response['Cache-Control'] = 'no-store'
        return response

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        row = self.get_object()
        IsolationNotice.objects.filter(pk=row.pk, read_at__isnull=True).update(
            read_at=timezone.now()
        )
        return Response({'read': True})
