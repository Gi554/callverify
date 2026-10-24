"""Escaped, self-contained transactional mail; no remote images or tracking."""

import re
from pathlib import Path
from urllib.parse import urlsplit
from django.conf import settings
from django.template import Context, Engine


def first_name(raw):
    """« camille.exemple » becomes « Camille Exemple »; an e-mail address is never shown."""
    raw = (raw or '').strip()
    if not raw or '@' in raw:
        return ''
    return re.sub(r'\s+', ' ', re.sub(r'[._-]+', ' ', raw)).title()[:60]


def site_name():
    host = urlsplit(getattr(settings, 'PORTAL_PUBLIC_URL', '') or '').hostname
    return host or ''


def layout(*, title, intro, action, url, notice, details=(), name=''):
    parsed = urlsplit(url)
    if (
        parsed.scheme not in (('http', 'https') if settings.DEBUG else ('https',))
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise ValueError('Invalid transactional email link')
    template = Engine(autoescape=True).from_string(
        (Path(__file__).parent / 'templates' / 'transactional.html').read_text(encoding='utf-8')
    )
    return template.render(
        Context(
            dict(
                title=title,
                intro=intro,
                action=action,
                url=url,
                notice=notice,
                details=details,
                name=first_name(name),
                site=site_name(),
            ),
            autoescape=True,
        )
    )
