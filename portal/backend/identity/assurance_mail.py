"""Pull minimal business events over HTTP; never connect to the Assurance database."""

from datetime import timedelta
from urllib.parse import urlsplit
import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from packages.access.mail_bridge import issue
from .models import Membership, AssuranceMailRelay, AssuranceMailCursor
from .email_layout import layout

STREAMS = {
    'incidents': (1, 'mail-events', 'events', 'eligible', 'assurance_follow_up'),
    'reminders': (
        2,
        'reminder-mail-events',
        'reminder_events',
        'reminder_eligible',
        'assurance_reminder',
    ),
    'escalations': (
        3,
        'escalation-mail-events',
        'escalation_events',
        'escalation_eligible',
        'assurance_escalation',
    ),
}


def fetch(path, operation, **claims):
    base = settings.ASSURANCE_INTERNAL_URL.rstrip('/')
    parsed = urlsplit(base)
    if (
        parsed.scheme not in ('http', 'https')
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError('Configure ASSURANCE_INTERNAL_URL')
    response = requests.get(
        base + path,
        headers={'Authorization': 'Bearer ' + issue(operation, **claims)},
        timeout=5,
        allow_redirects=False,
    )
    if response.status_code != 200:
        raise RuntimeError('Assurance mail bridge unavailable')
    return response.json()


def eligible(event, user, stream='incidents'):
    _, path, _, operation, _ = STREAMS[stream]
    data = fetch(
        f'/api/assurance/internal/{path}/{event}/{user}/', operation, event=event, user=user
    )
    if type(data.get('eligible')) is not bool:
        raise ValueError('Invalid bridge response')
    return data['eligible']


def sync(stream='incidents'):
    from .mail_queue import enqueue
    from .recovery import public_url

    if stream not in STREAMS:
        raise ValueError('Invalid mail stream')
    cursor_id, path, operation, _, guard_kind = STREAMS[stream]
    cursor, _ = AssuranceMailCursor.objects.get_or_create(pk=cursor_id)
    data = fetch(
        f'/api/assurance/internal/{path}/?after={cursor.after_id}', operation, after=cursor.after_id
    )
    events = data.get('events')
    if not isinstance(events, list) or len(events) > 100:
        raise ValueError('Invalid event batch')
    prepared = []
    previous = cursor.after_id
    for event in events:
        event_id = event.get('id')
        user_id = event.get('setter_id') if stream == 'incidents' else event.get('recipient_id')
        role = 'setter' if stream == 'incidents' else event.get('role')
        if role not in (('administrator',) if stream == 'escalations' else ('setter', 'advisor')):
            raise ValueError('Invalid recipient role')
        if (
            type(event_id) is not int
            or not previous < event_id <= 9223372036854775807
            or type(user_id) is not int
            or not (user_id == 0 if stream == 'escalations' else 0 < user_id <= 9223372036854775807)
        ):
            raise ValueError('Invalid event identity')
        created = parse_datetime(event.get('created_at', ''))
        if created is None or timezone.is_naive(created):
            raise ValueError('Invalid event date')
        appointment = None
        if stream == 'reminders' and event.get('kind') == 'report_missing':
            appointment = event.get('appointment_id')
            if (
                role != 'advisor'
                or type(appointment) is not int
                or not 0 < appointment <= 9223372036854775807
            ):
                raise ValueError('Invalid appointment reminder')
        prepared.append((event_id, user_id, created, role, appointment))
        previous = event_id
    counts = {'queued': 0, 'already_queued': 0, 'skipped': 0}
    expanded = []
    for event_id, user_id, created, role, appointment in prepared:
        recipients = (
            Membership.objects.filter(
                workspace='assurance', role='administrator', active=True, user__is_active=True
            )
            .order_by('user_id')
            .values_list('user_id', flat=True)
            if stream == 'escalations'
            else [user_id]
        )
        expanded.extend(
            (event_id, recipient, created, role, appointment) for recipient in recipients
        )
    for event_id, user_id, created, role, appointment in expanded:
        with transaction.atomic():
            user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
            if (
                not user
                or user.email.lower().endswith('.invalid')
                or not Membership.objects.filter(
                    user=user, workspace='assurance', role=role, active=True
                ).exists()
            ):
                counts['skipped'] += 1
                continue
            try:
                validate_email(user.email)
            except ValidationError:
                counts['skipped'] += 1
                continue
            if get_user_model().objects.filter(
                email__iexact=user.email, is_active=True
            ).count() != 1 or not timezone.now() - timedelta(
                days=7
            ) < created <= timezone.now() + timedelta(minutes=1):
                counts['skipped'] += 1
                continue
            relay, new = AssuranceMailRelay.objects.get_or_create(
                stream=stream, event_id=event_id, recipient_id=user_id
            )
            if not new:
                counts['already_queued'] += 1
                continue
            intro = (
                'Un rappel nécessite votre attention dans votre espace Assurance.'
                if stream == 'reminders'
                else 'Un signalement nécessite votre suivi dans votre espace Assurance.'
            )
            if stream == 'escalations':
                intro = 'Une situation durablement en attente nécessite votre supervision dans votre espace Assurance.'
            title = {
                'reminders': 'Votre prochain suivi vous attend',
                'incidents': 'Un suivi nécessite votre attention',
                'escalations': 'Une situation attend votre supervision',
            }[stream]
            notice = 'La lecture de cet e-mail ne clôture aucune tâche et ne renseigne aucun compte rendu. Retrouvez les détails uniquement après connexion à votre espace autorisé.'
            url = f'{public_url()}/crm'
            action = 'Consulter mon espace'
            if appointment:
                title = 'Un petit retour sur votre rendez-vous ?'
                intro = (
                    'Votre rendez-vous est terminé et son résultat reste à renseigner. '
                    'Quand vous avez un instant, indiquez si votre contact était présent, '
                    'si une vente ou un contrat a été conclu, et ajoutez vos notes utiles.'
                )
                action = 'Renseigner le rendez-vous'
                url += f'?workspace=assurance&appointment={appointment}'
                notice = (
                    'Une seule relance est prévue pour ce rendez-vous. '
                    'Si vous venez de renseigner le résultat, vous pouvez ignorer cet e-mail. '
                    'Le lien ouvre votre espace sécurisé ; aucune réponse n’est enregistrée automatiquement.'
                )
            relay.mail = enqueue(
                user=user,
                workspace='assurance',
                subject=f'Orvia CRM · Assurance — {title}',
                body=f'Bonjour,\n\n{intro}\n\n{action} : {url}\n\n{notice}\n\nOrvia CRM',
                html=layout(
                    title=title,
                    intro=intro,
                    action=action,
                    name=user.get_username(),
                    url=url,
                    notice=notice,
                    details=(('Espace', 'Assurance'),),
                ),
                recipient=user.email,
                guard={'kind': guard_kind, 'event': event_id, 'user': user_id, 'role': role},
                expires_at=created + timedelta(days=7),
            )
            relay.save(update_fields=['mail'])
            counts['queued'] += 1
    AssuranceMailCursor.objects.filter(pk=cursor_id, after_id=cursor.after_id).update(
        after_id=previous if len(events) == 100 else 0
    )
    return counts
