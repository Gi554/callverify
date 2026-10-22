"""Synthetic ORM fixtures for a NEW disposable common database only. No provider calls."""
from datetime import datetime, time, timedelta
import hashlib
import json
import os
from pathlib import Path
import random
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

DEMO = 'DÉMO — données entièrement fictives ; aucun appel réel.'
FIRST = ['Camille', 'Alex', 'Sam', 'Charlie', 'Noémie', 'Robin', 'Léa', 'Gabriel', 'Jade', 'Louis']
LAST = ['Moreau', 'Tremblay', 'Roy', 'Gagnon', 'Bouchard', 'Pelletier', 'Fortin', 'Lavoie']
STAGES = ['to_contact', 'in_progress', 'callback', 'interested', 'follow_up', 'closed']
RESULTS = ['voicemail', 'invalid_number', 'disconnected', 'not_interested', 'unreachable']


def identifier(seed, service, kind, index):
    return uuid5(NAMESPACE_URL, f'amx-demo/{seed}/{service}/{kind}/{index}')


def fingerprint(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


def phone(index):
    # Invalid NANP area code 000: cannot be confused with an assigned subscriber.
    return f'+1000{index:07d}'


def slot(index, total, now):
    zone = ZoneInfo('America/Toronto')
    spread = max(total, 80)
    position = index * spread // total
    day = now.astimezone(zone).date() + timedelta(days=position // 20 - spread // 40)
    return datetime.combine(day, time(8 + position % 20 // 2, 30 * (position % 2)), zone)


def task_dates(index, now):
    closed = index % 4 == 0
    due = now - timedelta(days=2) if closed else now + timedelta(days=index % 15 - 7, hours=index % 5)
    return due, now - timedelta(hours=1) if closed else None


def identities(password):
    from django.contrib.auth import get_user_model
    from portal.backend.identity.models import Membership
    User = get_user_model()
    if User.objects.exists() or Membership.objects.exists():
        raise ValueError('Portal must contain no accounts.')
    definitions = [('admin.demo', 'Administration Démo', [('assurance', 'administrator'), ('isolation', 'administrator')])]
    definitions += [(f'setter.demo{i:02d}', f'Setter Démo {i:02d}', [(space, 'setter') for space in ('assurance', 'isolation')]) for i in range(1, 11)]
    definitions += [(f'conseiller.demo{i:02d}', f'Conseiller Démo {i:02d}', [('assurance', 'advisor')]) for i in range(1, 6)]
    definitions += [(f'closer.demo{i:02d}', f'Closer Démo {i:02d}', [('isolation', 'closer')]) for i in range(1, 6)]
    definitions += [('client.demo', 'Client Isolation Démo', [('isolation', 'client')])]
    # One hash, twenty-two accounts; never a fixed password committed in source.
    from django.contrib.auth.hashers import make_password
    encoded = make_password(password)
    users = []
    for username, name, memberships in definitions:
        user = User.objects.create(username=username, first_name=name, email=username + '@example.invalid', password=encoded)
        Membership.objects.bulk_create([Membership(user=user, workspace=space, role=role) for space, role in memberships])
        users.append({'id': user.pk, 'username': username, 'name': name, 'memberships': memberships})
    return {'users': users, 'accounts': len(users), 'memberships': Membership.objects.count()}


def participants(context):
    users = context['users']
    def role(workspace, kind):
        return [user for user in users if [workspace, kind] in user['memberships']]
    return role('assurance', 'setter'), role('assurance', 'advisor'), role('isolation', 'closer'), role('isolation', 'client')[0]


def assurance(context, count, seed, now):
    from apps.assurance.backend.crm.models import (Contact, AdvisorAssignment, AdvisorSchedule, Appointment,
        AppointmentReport, FollowUpTask, ContactCallOutcome, ContactNote, BusinessAudit)
    from apps.assurance.backend.crm.qualification import snapshot
    if Contact.objects.exists() or AdvisorAssignment.objects.exists() or BusinessAudit.objects.exists():
        raise ValueError('Assurance business tables must be empty.')
    setters, advisors, _, _ = participants(context)
    assignments = AdvisorAssignment.objects.bulk_create([AdvisorAssignment(setter_id=setter['id'], setter_name=setter['name'],
        advisor_id=advisors[i % 5]['id'], advisor_name=advisors[i % 5]['name']) for i, setter in enumerate(setters)])
    AdvisorSchedule.objects.bulk_create([AdvisorSchedule(advisor_id=user['id']) for user in advisors])
    rng = random.Random(seed)
    contacts = []
    for i in range(count):
        setter = setters[i // 4 % 10]
        contacts.append(Contact(name=f'Démo {rng.choice(FIRST)} {rng.choice(LAST)} {i + 1:05d}', phone=phone(i + 1),
            email=f'prospect.assurance.{i + 1}@example.invalid', created_by_id=setter['id'], status=STAGES[i % len(STAGES)],
            assurance_qualification={'age': 25 + i % 55, 'profession': ['full_time', 'part_time', 'self_employed', 'retired', 'other'][i % 5],
                'marital_status': ['married', 'single', 'common_law', 'other'][i % 4], 'has_children': bool(i % 2),
                'homeowner': bool(i % 3), 'smoker': i % 5 == 0, 'has_advisor': i % 4 == 0,
                'insurances': [['none_known'], ['life'], ['life', 'disability'], ['group'], ['critical_illness']][i % 5],
                'additional_notes': DEMO, 'advisor_notes': DEMO + ' Qualification préparée pour la recette.'}))
    Contact.objects.bulk_create(contacts, batch_size=1000)
    appointments = []; notes = []; tasks = []; outcomes = []; reports = []
    appointment_total = (count + 3) // 4
    by_contact = {}
    for i, contact in enumerate(contacts):
        if i % 4: continue
        k = i // 4; assignment = assignments[k % 10]
        starts = slot(k, appointment_total, now)
        contact.assigned_advisor_id = assignment.advisor_id
        contact.status = 'appointment_booked'
        captured = snapshot(contact); captured['captured_at'] = min(now, starts - timedelta(days=2)).isoformat()
        row = Appointment(contact=contact, assignment=assignment, request_id=identifier(seed, 'assurance', 'appointment', i),
            fingerprint=fingerprint(i), setter_id=assignment.setter_id, setter_name=assignment.setter_name,
            advisor_id=assignment.advisor_id, advisor_name=assignment.advisor_name, booked_by_id=assignment.setter_id,
            starts_at=starts, ends_at=starts + timedelta(minutes=30), timezone='America/Toronto',
            status='cancelled' if k % 10 == 0 else 'scheduled', qualification_snapshot=captured,
            reschedule_count=1 if k % 9 == 0 else 0, rescheduled_at=starts - timedelta(days=1) if k % 9 == 0 else None)
        appointments.append(row); by_contact[contact.pk] = (k, row)
    Appointment.objects.bulk_create(appointments, batch_size=1000)
    for i, contact in enumerate(contacts):
        setter = setters[i // 4 % 10]
        appointment_entry = by_contact.get(contact.pk); appointment = appointment_entry[1] if appointment_entry else None
        if appointment and appointment.status == 'scheduled' and appointment.ends_at < now and appointment_entry[0] % 7:
            performed = appointment_entry[0] % 4 != 0
            reports.append(AppointmentReport(appointment=appointment, performed=performed, outcome='performed' if performed else 'absent',
                author_id=appointment.advisor_id, note=DEMO))
            contact.status = 'appointment_done' if performed else 'incident'
        task = None
        if i % 3 == 0:
            due, closed = task_dates(i // 3, now)
            task = FollowUpTask(contact=contact, setter_id=setter['id'], request_id=identifier(seed, 'assurance', 'task', i),
                fingerprint=fingerprint(i), reason=DEMO + ' Rappel de recette.', priority='high' if i % 5 == 0 else 'normal',
                due_at=due, closed_at=closed, closed_by_id=setter['id'] if closed else None, resolution=DEMO if closed else '')
            tasks.append(task)
        result = 'appointment_booked' if appointment and appointment.status == 'scheduled' else 'callback' if task else RESULTS[i % len(RESULTS)]
        outcomes.append((contact, setter, result, appointment if result == 'appointment_booked' else None, task if result == 'callback' else None))
        notes.append(ContactNote(contact=contact, author_id=setter['id'], request_id=identifier(seed, 'assurance', 'note', i),
            channel='internal', body=DEMO + f' Scénario prospect {i + 1}.'))
    AppointmentReport.objects.bulk_create(reports, batch_size=1000)
    FollowUpTask.objects.bulk_create(tasks, batch_size=1000)
    ContactNote.objects.bulk_create(notes, batch_size=1000)
    ContactCallOutcome.objects.bulk_create([ContactCallOutcome(contact=contact, setter_id=setter['id'], result=result, appointment=appointment,
        task=task, note=DEMO, request_id=identifier(seed, 'assurance', 'outcome', i), fingerprint=fingerprint(i))
        for i, (contact, setter, result, appointment, task) in enumerate(outcomes)], batch_size=1000)
    Contact.objects.bulk_update(contacts, ['status', 'assigned_advisor_id'], batch_size=1000)
    BusinessAudit.objects.create(actor_id=context['users'][0]['id'], action='demo.seeded', object_id=0,
        metadata={'synthetic': True, 'seed': seed, 'contacts': count})
    return {'contacts': count, 'appointments': len(appointments), 'reports': len(reports), 'tasks': len(tasks), 'notes': len(notes), 'declared_results': len(outcomes)}


def isolation(context, count, seed, now):
    from core.models import (AdminUser, Campaign, Prospect, IsolationVisit, IsolationVisitResult,
        IsolationVisitCalendar, IsolationFollowUp, ProspectActivity, AuditEvent)
    from core.isolation_c2 import captured
    if AdminUser.objects.exists() or Campaign.objects.exists() or Prospect.objects.exists():
        raise ValueError('Isolation business tables must be empty.')
    setters, _, closers, client = participants(context)
    owner = AdminUser(username='demo.legacy.inactive', is_active=False); owner.set_unusable_password(); owner.save()
    campaigns = Campaign.objects.bulk_create([Campaign(owner=owner, name=f'DÉMO — Isolation campagne {i + 1}',
        portal_workspace='isolation', portal_owner_id=context['users'][0]['id'], source=DEMO, purpose='Recette synthétique') for i in range(6)])
    IsolationVisitCalendar.objects.create(client_id=client['id'])
    rng = random.Random(seed + 1); prospects = []
    for i in range(count):
        setter = setters[i // 4 % 10]; name = f'Démo {rng.choice(FIRST)} {rng.choice(LAST)} {i + 1:05d}'
        prospects.append(Prospect(campaign=campaigns[i % 6], name=name, reference=f'DEMO-{seed}-{i + 1:05d}', raw_phone=phone(i + 1),
            assigned_setter_id=setter['id'], assigned_setter_name=setter['name'],
            commercial_status=['to_contact', 'in_progress', 'callback', 'interested', 'not_interested', 'unreachable'][i % 6],
            validity='indeterminate', reason=DEMO, compliance='review', compliance_reason='Recette uniquement, aucune autorisation réelle.',
            c2={'full_name': name, 'phone': phone(i + 1), 'address': f'{i + 1} rue Fictive (DÉMO)', 'city': 'Ville Démo',
                'postal_code': 'H1A 1A1', 'attic_accessible': bool(i % 2), 'monthly_electricity': str(80 + i % 240) + '.00',
                'construction_year': 1950 + i % 70, 'age': 30 + i % 50}))
    Prospect.objects.bulk_create(prospects, batch_size=1000)
    visits = []; reports = []; tasks = []; activities = []; by_prospect = {}; task_map = {}
    for i, prospect in enumerate(prospects):
        if i % 4: continue
        k = i // 4; setter = setters[k % 10]; closer = closers[k % 5]
        starts = slot(k, (count + 3) // 4, now)
        snap = captured(prospect); snap['captured_at'] = min(now, starts - timedelta(days=2)).isoformat()
        visit = IsolationVisit(prospect=prospect, request_id=identifier(seed, 'isolation', 'visit', i), fingerprint=fingerprint(i),
            client_id=client['id'], client_name=client['name'], setter_id=setter['id'], setter_name=setter['name'], booked_by_id=setter['id'],
            closer_id=closer['id'], closer_name=closer['name'], c2_snapshot=snap, starts_at=starts, ends_at=starts + timedelta(minutes=30),
            timezone='America/Toronto', status='cancelled' if k % 10 == 0 else 'scheduled')
        visits.append(visit); by_prospect[prospect.pk] = (k, visit); prospect.commercial_status = 'interested'
    IsolationVisit.objects.bulk_create(visits, batch_size=1000)
    for i, prospect in enumerate(prospects):
        setter = setters[i // 4 % 10]; entry = by_prospect.get(prospect.pk); visit = entry[1] if entry else None
        if visit and visit.status == 'scheduled' and visit.ends_at < now and entry[0] % 7:
            performed = entry[0] % 4 != 0; closed = performed and entry[0] % 3 == 0
            reports.append(IsolationVisitResult(visit=visit, author_closer_id=visit.closer_id, performed=performed, closed=closed,
                outcome='closed' if closed else 'completed' if performed else 'not_performed', note=DEMO))
            prospect.commercial_status = 'interested' if performed else 'callback'
        if i % 3 == 0:
            due, closed_at = task_dates(i // 3, now)
            task = IsolationFollowUp(prospect=prospect, request_id=identifier(seed, 'isolation', 'task', i), fingerprint=fingerprint(i),
                created_by_id=setter['id'], note=DEMO, due_at=due, closed_at=closed_at,
                closed_by_id=setter['id'] if closed_at else None, resolution=DEMO if closed_at else '')
            tasks.append(task); task_map[prospect.pk] = task
            prospect.callback_at = None if closed_at else due
    IsolationVisitResult.objects.bulk_create(reports, batch_size=1000)
    IsolationFollowUp.objects.bulk_create(tasks, batch_size=1000)
    for i, prospect in enumerate(prospects):
        setter = setters[i // 4 % 10]; entry = by_prospect.get(prospect.pk); visit = entry[1] if entry else None
        task = task_map.get(prospect.pk)
        result = 'appointment_booked' if visit and visit.status == 'scheduled' else 'callback' if task else RESULTS[i % len(RESULTS)]
        changes = {'result': result, 'phone': prospect.raw_phone, 'synthetic': True}
        if result == 'appointment_booked': changes['appointment_id'] = visit.pk
        if result == 'callback': changes.update(task_id=task.pk, due_at=task.due_at.isoformat())
        activities.append(ProspectActivity(prospect=prospect, request_id=identifier(seed, 'isolation', 'outcome', i), fingerprint=fingerprint(i),
            author_portal_id=setter['id'], author_role='setter', kind='call_result', body=DEMO, changes=changes))
        activities.append(ProspectActivity(prospect=prospect, request_id=identifier(seed, 'isolation', 'note', i), fingerprint=fingerprint(i),
            author_portal_id=setter['id'], author_role='setter', kind='note', body=DEMO + ' Note de suivi synthétique.'))
    ProspectActivity.objects.bulk_create(activities, batch_size=1000)
    Prospect.objects.bulk_update(prospects, ['commercial_status', 'callback_at'], batch_size=1000)
    AuditEvent.objects.create(action='demo.seeded', metadata={'actor_portal_id': context['users'][0]['id'], 'synthetic': True, 'seed': seed, 'prospects': count})
    return {'prospects': count, 'campaigns': len(campaigns), 'appointments': len(visits), 'reports': len(reports),
            'tasks': len(tasks), 'activities': len(activities)}


def main():
    from django.conf import settings
    from django.db import connection, transaction
    from django.utils import timezone
    service = os.environ['CRM_DB_SCHEMA']
    manifest = json.loads(Path(os.environ['CRM_DEMO_CONTEXT']).read_text(encoding='utf-8'))
    if not settings.DEBUG or os.getenv('CRM_DEMO_MODE') != 'true' or manifest.get('disposable') is not True:
        raise ValueError('Disposable demo configuration required.')
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database(), current_schema(), current_user')
        name, schema, user = cursor.fetchone()
    if not name.startswith('amx_rehearsal_') or name != manifest['database'] or schema != service or user != manifest['services'][service]['user']:
        raise ValueError('Demo target mismatch.')
    count = manifest['demo']['contacts_per_space']
    if not 40 <= count <= 20000: raise ValueError('Count outside supported demo range.')
    with transaction.atomic():
        if service == 'portal': result = identities(manifest['demo']['password'])
        else:
            fn = assurance if service == 'assurance' else isolation
            result = fn(manifest['demo'], count, manifest['demo']['seed'], timezone.now())
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()
    main()
