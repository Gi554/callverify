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
    if response.status_code != 200 or len(response.content) > 200000:
        raise RuntimeError('Isolation mail bridge unavailable')
    return response.json()


def eligible(event, user):
    data = fetch(
        f'/api/internal/isolation/mail-events/{event}/{user}/',
        'mail_eligible',
        event=event,
        user=user,
    )
    if type(data.get('eligible')) is not bool:
        raise ValueError('Invalid eligibility')
    return data['eligible']


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
        prepared.append((pk, user, visit, name, row['kind'], *stamps))
        previous = pk
    counts = {'queued': 0, 'existing': 0, 'skipped': 0}
    for pk, user_id, visit, name, kind, created, starts in prepared:
        with transaction.atomic():
            user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
            if (
                not user
                or user.email.lower().endswith('.invalid')
                or not Membership.objects.filter(
                    user=user, workspace='isolation', role='client', active=True
                ).exists()
                or get_user_model().objects.filter(email__iexact=user.email, is_active=True).count()
                != 1
                or not timezone.now() - timedelta(days=7)
                < created
                <= timezone.now() + timedelta(minutes=1)
            ):
                counts['skipped'] += 1
                continue
            try:
                validate_email(user.email)
            except ValidationError:
                counts['skipped'] += 1
                continue
            relay, new = IsolationMailRelay.objects.get_or_create(
                event_id=pk, defaults={'recipient_id': user_id}
            )
            if not new:
                counts['existing'] += 1
                continue
            when = starts.astimezone(ZoneInfo('America/Toronto')).strftime('%d/%m/%Y à %H:%M')
            title = (
                'Une nouvelle visite vous attend'
                if kind == 'booked'
                else 'Un petit retour sur votre visite ?'
            )
            intro = (
                f'Une visite avec {name} est programmée le {when} (heure du Québec). Retrouvez la qualification et les informations utiles dans votre espace.'
                if kind == 'booked'
                else f'Le résultat de la visite avec {name}, prévue le {when} (heure du Québec), reste à renseigner. Merci de confirmer si elle a été tenue et si une vente a été conclue.'
            )
            url = f'{public_url()}/crm?workspace=isolation&visit={visit}'
            notice = 'Ce lien ouvre votre espace sécurisé. La lecture de cet e-mail ne renseigne aucun résultat. Si vous venez de le compléter, vous pouvez ignorer ce rappel.'
            relay.mail = enqueue(
                user=user,
                workspace='isolation',
                subject='Orvia CRM · Isolation — ' + title,
                body=f'Bonjour,\n\n{intro}\n\nConsulter la visite : {url}\n\n{notice}\n\nOrvia CRM',
                html=layout(
                    title=title,
                    intro=intro,
                    action='Consulter la visite',
                    name=user.get_username(),
                    url=url,
                    notice=notice,
                    details=(('Prospect', name), ('Date de visite', when + ' (Québec)')),
                ),
                recipient=user.email,
                guard={'kind': 'isolation_notice', 'event': pk, 'user': user_id},
                expires_at=created + timedelta(days=7),
            )
            relay.save(update_fields=['mail'])
            counts['queued'] += 1
    IsolationMailCursor.objects.filter(pk=1, after_id=cursor.after_id).update(
        after_id=previous if len(rows) == 100 else 0
    )
    return counts
