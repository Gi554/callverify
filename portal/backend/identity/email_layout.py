"""Escaped, self-contained transactional mail; no remote images or tracking."""

from pathlib import Path
from urllib.parse import urlsplit
from django.conf import settings
from django.template import Context, Engine


def layout(*, title, intro, action, url, notice, details=()):
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
            ),
            autoescape=True,
        )
    )
