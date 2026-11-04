"""Minimal signed Isolation events into the encrypted SMTP outbox."""

from datetime import timedelta
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from packages.access.isolation_events import issue
from .models import Membership, IsolationMailRelay, IsolationMailCursor
from .email_layout import layout


def fetch(path, operation, **claims):
    base = settings.ISOLATION_INTERNAL_URL.rstrip('/')
    parsed = urlsplit(base)
    if (
        parsed.scheme not in ('http', 'https')
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError('Isolation internal URL required')
    response = requests.get(
        base + path,
        headers={
            'Authorization': 'Bearer ' + issue(operation, **claims),
            'X-Forwarded-Proto': 'https',
        },
        timeout=5,
        allow_redirects=False,
    )
    if response.status_code != 200 or len(response.content) > 1000000:
        raise RuntimeError('Isolation mail bridge unavailable')
    return response.json()


def eligible(event, user, recipient=None):
    data = fetch(
        f'/api/internal/isolation/mail-events/{event}/{user}/',
        'mail_eligible',
        event=event,
        user=user,
    )
    if type(data.get('eligible')) is not bool:
        raise ValueError('Invalid eligibility')
    return data['eligible'] and (recipient is None or data.get('prospect_email') == recipient)


def booking_sections(row, starts, ends):
    fields = row.get('qualification', {})
    if not isinstance(fields, dict):
        raise ValueError('Invalid qualification')
    if any(
        type(value) not in (str, bool, int, float, type(None)) or len(str(value)) > 1500
        for value in fields.values()
    ):
        raise ValueError('Invalid qualification value')
    for key in ('setter_name', 'reference', 'campaign_name'):
        if not isinstance(row.get(key, ''), str) or len(row.get(key, '')) > 500:
            raise ValueError('Invalid booking detail')

    def pairs(spec):
        return tuple(
            (
                label,
                'Oui' if fields[key] is True else 'Non' if fields[key] is False else fields[key],
            )
            for key, label in spec
            if fields.get(key) is not None and fields.get(key) != ''
        )

    prospect = (('Nom', fields.get('full_name') or row['prospect_name']),) + pairs(
        (
            ('phone', 'Téléphone'),
            ('address', 'Adresse'),
            ('city', 'Ville'),
            ('postal_code', 'Code postal'),
            ('email', 'Courriel'),
        )
    )
    local = starts.astimezone(ZoneInfo('America/Toronto'))
    appointment = (
        ('Date', local.strftime('%d/%m/%Y')),
        ('Heure', local.strftime('%H:%M') + ' (heure du Québec)'),
    )
    if ends:
        appointment += (('Fin', ends.astimezone(ZoneInfo('America/Toronto')).strftime('%H:%M')),)
    appointment += tuple(
        (label, row[key])
        for key, label in (
            ('setter_name', 'Setter'),
            ('campaign_name', 'Campagne'),
            ('reference', 'Référence'),
        )
        if row.get(key)
    )
    qualification = pairs(
        (
            ('attic_accessible', 'Grenier accessible'),
            ('monthly_electricity', 'Coût mensuel d’électricité (CAD)'),
            ('construction_year', 'Année de construction'),
            ('age', 'Âge du client'),
        )
    )
    qualification = qualification or (('Qualification', 'Aucune information renseignée'),)
    return (
        ('Informations du prospect', prospect),
        ('Informations du rendez-vous', appointment),
        ('Informations de qualification', qualification),
    )


def sync():
    from .mail_queue import enqueue
    from .recovery import public_url

    cursor, _ = IsolationMailCursor.objects.get_or_create(pk=1)
    data = fetch(
        f'/api/internal/isolation/mail-events/?after={cursor.after_id}',
        'mail_events',
        after=cursor.after_id,
    )
    rows = data.get('events')
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError('Invalid event batch')
    prepared = []
    previous = cursor.after_id
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid event')
        pk, user, visit = [row.get(key) for key in ('id', 'recipient_id', 'visit_id')]
        if (
            any(
                type(value) is not int or not 0 < value <= 9223372036854775807
                for value in (pk, user, visit)
            )
            or pk <= previous
        ):
            raise ValueError('Invalid identity')
        name = row.get('prospect_name')
        if (
            not isinstance(name, str)
            or not name.strip()
            or len(name) > 500
            or row.get('kind') not in ('booked', 'result_due')
        ):
            raise ValueError('Invalid event content')
        stamps = []
        for field in ('created_at', 'starts_at'):
            stamp = row.get(field)
            value = parse_datetime(stamp) if isinstance(stamp, str) else None
            if value is None or timezone.is_naive(value):
                raise ValueError('Invalid event date')
            stamps.append(value)
        email = row.get('prospect_email', '')
        address = row.get('visit_address', '')
        if (
            not isinstance(email, str)
            or len(email) > 254
            or not isinstance(address, str)
            or len(address) > 750
        ):
            raise ValueError('Invalid prospect confirmation')
        end = parse_datetime(row['ends_at']) if isinstance(row.get('ends_at'), str) else None
        if email and (end is None or timezone.is_naive(end) or end <= stamps[1]):
            raise ValueError('Invalid visit end')
        sections = booking_sections(row, stamps[1], end) if row['kind'] == 'booked' else ()
        prepared.append((pk, user, visit, name, row['kind'], *stamps, sections))
        previous = pk
    counts = {'queued': 0, 'existing': 0, 'skipped': 0}
    reminders = []

    def valid_address(email):
        try:
            validate_email(email)
            return not email.lower().endswith('.invalid')
        except ValidationError:
            return False

    for pk, user_id, visit, name, kind, created, starts, sections in prepared:
        with transaction.atomic():
            user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
            if (
                not user
                or not Membership.objects.filter(
                    user=user, workspace='isolation', role='client', active=True
                ).exists()
                or not timezone.now() - timedelta(days=7)
                < created
                <= timezone.now() + timedelta(minutes=1)
            ):
                counts['skipped'] += 1
                continue
            client_valid = (
                valid_address(user.email)
                and get_user_model()
                .objects.filter(email__iexact=user.email, is_active=True)
                .count()
                == 1
            )
            if not client_valid:
                counts['skipped'] += 1
                continue
            relay, _ = IsolationMailRelay.objects.get_or_create(
                event_id=pk, defaults={'recipient_id': user_id}
            )
            # Serialize the client queue even when relay jobs overlap.
            relay = IsolationMailRelay.objects.select_for_update().get(pk=relay.pk)
            if relay.recipient_id != user_id:
                raise ValueError('Event recipient changed')
            when = starts.astimezone(ZoneInfo('America/Toronto')).strftime('%d/%m/%Y à %H:%M')
            if client_valid:
                if relay.mail_id:
                    counts['existing'] += 1
                else:
                    title = (
                        'Une nouvelle visite vient d’être programmée'
                        if kind == 'booked'
                        else 'Un petit retour sur votre visite ?'
                    )
                    intro = (
                        'Une nouvelle visite vient d’être programmée dans votre espace ORVIA. Voici les informations concernant ce rendez-vous.'
                        if kind == 'booked'
                        else f'Le résultat de la visite avec {name}, prévue le {when} (heure du Québec), reste à renseigner. Merci de confirmer si elle a été tenue et si une vente a été conclue.'
                    )
                    url = f'{public_url()}/crm?workspace=isolation&visit={visit}'
                    notice = 'Ce lien ouvre votre espace sécurisé. La lecture de cet e-mail ne renseigne aucun résultat. Si vous venez de le compléter, vous pouvez ignorer ce rappel.'
                    greeting = user.first_name.strip() if kind == 'booked' else ''
                    summary = '\n\n'.join(
                        heading + '\n' + '\n'.join(f'{label} : {value}' for label, value in items)
                        for heading, items in sections
                    )
                    closing = 'Martinien' if kind == 'booked' else 'Orvia CRM'
                    relay.mail = enqueue(
                        user=user,
                        workspace='isolation',
                        subject=title if kind == 'booked' else 'Orvia CRM · Isolation — ' + title,
                        body=f'Bonjour{(" " + greeting) if greeting else ""},\n\n{intro}\n\n{summary or (name + " · " + when)}\n\nAccéder à mon espace ORVIA : {url}\n\n{notice}\n\nCordialement,\n{closing}',
                        html=layout(
                            title=title,
                            intro=intro,
                            action='Accéder à mon espace ORVIA',
                            name=greeting,
                            url=url,
                            notice=notice,
                            details=()
                            if sections
                            else (('Prospect', name), ('Date de visite', when + ' (Québec)')),
                            sections=sections,
                            signature=closing if kind == 'booked' else 'l’équipe Orvia CRM',
                        ),
                        recipient=user.email,
                        guard={'kind': 'isolation_notice', 'event': pk, 'user': user_id},
                        expires_at=created + timedelta(days=7),
                    )
                    relay.save(update_fields=['mail'])
                    counts['queued'] += 1
                    if kind == 'result_due':
                        reminders.append((user, pk, starts))
    IsolationMailCursor.objects.filter(pk=1, after_id=cursor.after_id).update(
        after_id=previous if len(rows) == 100 else 0
    )
    for user, event, starts in reminders:
        try:
            from .isolation_sms import remind_client

            remind_client(user, event, starts)
        except Exception:
            # A failed reminder SMS never blocks the e-mail queue; no exception text is kept.
            pass
    return counts
