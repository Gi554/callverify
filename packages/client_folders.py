"""Read-only administrator portfolios; no cross-database joins or role impersonation."""

from django.db.models import Case, When, Value, CharField, Count, Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


def scope(workspace, client_id):
    if workspace == 'assurance':
        from apps.assurance.backend.crm.models import Appointment, Contact

        appointments = Appointment.objects.filter(advisor_id=client_id)
        contacts = Contact.objects.filter(
            Q(assigned_advisor_id=client_id) | Q(appointments__advisor_id=client_id)
        ).distinct()
        return appointments, contacts, 'contact', 'report', 'sale_concluded', 'status'
    from core.models import IsolationVisit, Prospect

    appointments = IsolationVisit.objects.filter(client_id=client_id)
    contacts = Prospect.objects.filter(visits__client_id=client_id).distinct()
    return appointments, contacts, 'prospect', 'result', 'closed', 'commercial_status'


def classified(rows, relation, now):
    cases = [When(status='cancelled', then=Value('cancelled'))]
    cases.append(When(**{f'{relation}__performed': True}, then=Value('performed')))
    if relation == 'report':
        cases.append(When(**{f'{relation}__outcome': 'absent'}, then=Value('absent')))
    cases.extend(
        [
            When(**{f'{relation}__performed': False}, then=Value('not_performed')),
            When(ends_at__lte=now, then=Value('report_due')),
        ]
    )
    if relation == 'report':
        cases.append(When(reschedule_count__gt=0, then=Value('rescheduled')))
    return rows.annotate(
        folder_status=Case(*cases, default=Value('scheduled'), output_field=CharField())
    )


def work(workspace, contacts, appointments):
    ids = contacts.values('pk')
    if workspace == 'assurance':
        from apps.assurance.backend.crm.models import ContactCallOutcome, FollowUpTask

        calls = ContactCallOutcome.objects.filter(contact_id__in=ids)
        tasks = FollowUpTask.objects.filter(Q(contact_id__in=ids) | Q(appointment__in=appointments))
    else:
        from core.models import ProspectActivity, IsolationFollowUp

        calls = ProspectActivity.objects.filter(prospect_id__in=ids, kind='call_result')
        tasks = IsolationFollowUp.objects.filter(prospect_id__in=ids)
    return calls, tasks


def summary(workspace, client_id, now):
    appointments, contacts, _, relation, sale, status = scope(workspace, client_id)
    states = dict(
        classified(appointments, relation, now)
        .order_by()
        .values('folder_status')
        .annotate(total=Count('pk'))
        .values_list('folder_status', 'total')
    )
    sales = appointments.filter(
        status='scheduled', **{f'{relation}__performed': True, f'{relation}__{sale}': True}
    ).count()
    statuses = list(contacts.order_by().values(status).annotate(total=Count('pk', distinct=True)))
    calls, tasks = work(workspace, contacts, appointments)
    if workspace == 'assurance':
        from apps.assurance.backend.crm.pipeline import pipeline

        labels = {stage['key']: stage['label'] for stage in pipeline().stages}
    else:
        from core.isolation_activity import STATUSES

        labels = STATUSES
    return {
        'id': client_id,
        'prospects': contacts.count(),
        'appointments': sum(states.values()),
        'statuses': states,
        'sales': sales,
        'call_results': calls.count(),
        'tasks': tasks.count(),
        'open_tasks': tasks.filter(closed_at__isnull=True).count(),
        'overdue_tasks': tasks.filter(closed_at__isnull=True, due_at__lt=now).count(),
        'prospect_statuses': [
            {
                'status': row[status],
                'label': labels.get(row[status], row[status]),
                'total': row['total'],
            }
            for row in statuses
        ],
    }


def dossier_rows(workspace, client_id, params, now):
    appointments, contacts, resource, relation, _, status = scope(workspace, client_id)
    section = params.get('section', 'prospects')
    term = params.get('search', '').strip()[:250]
    if section == 'prospects':
        rows = contacts
        if params.get('status'):
            rows = rows.filter(**{status: params['status'][:40]})
        if term:
            phone = 'phone' if workspace == 'assurance' else 'raw_phone'
            rows = rows.filter(Q(name__icontains=term) | Q(**{f'{phone}__icontains': term}))
        rows = rows.order_by('-pk')
    elif section == 'appointments':
        rows = classified(appointments, relation, now).select_related(resource, relation)
        if term:
            rows = rows.filter(**{f'{resource}__name__icontains': term})
        state = params.get('status', '')
        if state:
            if state not in (
                'scheduled',
                'rescheduled',
                'performed',
                'absent',
                'not_performed',
                'report_due',
                'cancelled',
            ):
                raise ValidationError('Statut de rendez-vous invalide.')
            rows = rows.filter(folder_status=state)
        rows = rows.order_by('-starts_at', '-pk')
    elif section in ('calls', 'tasks'):
        calls, tasks = work(workspace, contacts, appointments)
        rows = calls if section == 'calls' else tasks
        if term:
            if section == 'tasks' and workspace == 'assurance':
                rows = rows.filter(
                    Q(contact__name__icontains=term) | Q(appointment__contact__name__icontains=term)
                )
            else:
                rows = rows.filter(**{f'{resource}__name__icontains': term})
        rows = rows.order_by('-created_at', '-pk')
        if workspace == 'assurance' and section == 'tasks':
            rows = rows.select_related('contact', 'appointment__contact')
        else:
            rows = rows.select_related(resource)
    else:
        raise ValidationError('Section inconnue.')
    return rows, (resource, relation, status, section)


def serialize_rows(page, workspace, context, now):
    resource, relation, status, section = context
    output = []
    for row in page:
        if section == 'prospects':
            output.append(
                {
                    'id': row.pk,
                    'name': row.name,
                    'phone': row.phone if workspace == 'assurance' else row.raw_phone,
                    'status': getattr(row, status),
                }
            )
        elif section == 'appointments':
            person = getattr(row, resource)
            report = getattr(row, relation, None)
            output.append(
                {
                    'id': row.pk,
                    'contact_id': person.pk,
                    'name': person.name,
                    'starts_at': row.starts_at,
                    'ends_at': row.ends_at,
                    'timezone': row.timezone,
                    'status': row.folder_status,
                    'setter_id': row.setter_id,
                    'setter_name': row.setter_name,
                    'booked_by_id': row.booked_by_id,
                    'closer_name': getattr(row, 'closer_name', ''),
                    'note': report.note if report else '',
                    'report_by_id': (
                        getattr(report, 'author_id', None)
                        or getattr(report, 'author_closer_id', None)
                        or getattr(report, 'author_client_id', None)
                    ),
                    'reported_at': report.created_at if report else None,
                    'performed': report.performed if report else None,
                    'sale_concluded': (
                        getattr(report, 'sale_concluded', getattr(report, 'closed', None))
                        if report
                        else None
                    ),
                }
            )
        else:
            person = getattr(row, resource, None)
            if person is None:
                person = row.appointment.contact
            if section == 'calls':
                result = row.result if workspace == 'assurance' else row.changes.get('result', '')
                note = row.note if workspace == 'assurance' else row.body
                actor = row.setter_id if workspace == 'assurance' else row.author_portal_id
            else:
                result = 'closed' if row.closed_at else ('overdue' if row.due_at < now else 'open')
                note = row.reason if workspace == 'assurance' else row.note
                actor = row.setter_id if workspace == 'assurance' else row.created_by_id
            output.append(
                {
                    'id': row.pk,
                    'contact_id': person.pk,
                    'name': person.name,
                    'created_at': row.created_at,
                    'status': result,
                    'note': note,
                    'actor_id': actor,
                    **(
                        {
                            'due_at': row.due_at,
                            'resolution': row.resolution,
                            'closed_by_id': row.closed_by_id,
                        }
                        if section == 'tasks'
                        else {}
                    ),
                }
            )
    return output


def folders(request, workspace, client_id=None):
    if request.user.role != 'administrator':
        raise PermissionDenied('Dossiers clients réservés aux administrateurs.')
    now = timezone.now()
    if client_id is None:
        raw = request.query_params.get('ids', '').split(',')
        if not 1 <= len(raw) <= 25 or any(
            not item.isascii() or not item.isdigit() or len(item) > 18 or int(item) < 1
            for item in raw
        ):
            raise ValidationError('De 1 à 25 identifiants clients attendus.')
        response = Response(
            {'results': [summary(workspace, pk, now) for pk in dict.fromkeys(map(int, raw))]}
        )
    else:
        rows, context = dossier_rows(workspace, client_id, request.query_params, now)
        pager = PageNumberPagination()
        pager.page_size = 25
        page = pager.paginate_queryset(rows, request)
        output = serialize_rows(page, workspace, context, now)
        response = pager.get_paginated_response(output)
        response.data['summary'] = summary(workspace, client_id, now)
    response['Cache-Control'] = 'no-store'
    return response
