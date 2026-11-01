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
from .models import IsolationNotice, IsolationFollowUp


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
    from .isolation_client_followups import sync_client_followup

    sync_client_followup(visit, report)
    existing_task = IsolationFollowUp.objects.filter(absence_visit=visit).first()
    if report.performed or report.follow_up_owner == 'client':
        if existing_task and existing_task.closed_at is None:
            existing_task.closed_at = timezone.now()
            existing_task.closed_by_id = actor.pk
            existing_task.resolution = 'Suivi repris par le client ou présence corrigée.'
            existing_task.revision += 1
            existing_task.save(
                update_fields=['closed_at', 'closed_by_id', 'resolution', 'revision']
            )
            sync(prospect)
    else:
        task, created = IsolationFollowUp.objects.get_or_create(
            absence_visit=visit,
            defaults={
                'prospect': prospect,
                'request_id': uuid4(),
                'created_by_id': None,
                'fingerprint': hashlib.sha256(f'absence:{visit.pk}'.encode()).hexdigest(),
                'note': 'Visite non tenue : rappeler le prospect pour programmer une nouvelle visite.',
                'due_at': report.follow_up_at or timezone.now() + timedelta(hours=24),
            },
        )
        reopen = (
            not created
            and task.closed_at
            and previous
            and (previous.get('performed') or previous.get('follow_up_owner') == 'client')
        )
        if (
            created
            or reopen
            or (
                previous
                and previous.get('follow_up_at')
                != (report.follow_up_at.isoformat() if report.follow_up_at else None)
            )
        ):
            task.due_at = report.follow_up_at or timezone.now() + timedelta(hours=24)
        if reopen:
            task.closed_at = None
            task.closed_by_id = None
            task.resolution = ''
        if created or not task.closed_at:
            task.note = '\n'.join(
                filter(
                    None,
                    [
                        'Visite non tenue : rappeler le prospect pour programmer une nouvelle visite.',
                        report.absence_reason,
                        report.note,
                    ],
                )
            )
            task.revision += not created
            task.save(
                update_fields=[
                    'closed_at',
                    'closed_by_id',
                    'resolution',
                    'due_at',
                    'note',
                    'revision',
                ]
            )
        sync(prospect)
    if not report.performed and report.follow_up_owner == 'client':
        return
    if (
        previous
        and previous['performed'] == report.performed
        and previous.get('closed') == report.closed
        and previous.get('follow_up_owner', 'setter') == report.follow_up_owner
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
        from django.db.models import F

        rows = rows.filter(
            ~Q(kind='personal_followup')
            | Q(
                kind='personal_followup',
                visit__client_followup__closed_at__isnull=True,
                visit__client_followup__due_at__lte=timezone.now(),
                anchor_at=F('visit__client_followup__due_at'),
            )
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
            'personal_followup': 'Relance personnelle à effectuer',
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
