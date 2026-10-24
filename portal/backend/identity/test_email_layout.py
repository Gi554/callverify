from datetime import timedelta
from html.parser import HTMLParser
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from .email_layout import layout
from .mail_queue import cipher, dispatch, enqueue
from .models import PortalMail
import json


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag == 'a':
            self.links.append(dict(attrs)['href'])


@override_settings(
    DEBUG=True, PORTAL_MAIL_KEY='', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
)
class EmailLayoutTests(TestCase):
    def message(self, **changes):
        values = dict(
            title='Un accès sécurisé',
            intro='Bonjour <script>secret</script>',
            action='Ouvrir',
            url='https://crm.example.test/crm#invite=demo:token&test=1',
            notice='Usage unique',
            details=(('Identifiant', '"><img src=x onerror=alert(1)>'),),
        )
        return layout(**(values | changes))

    def test_html_escapes_all_dynamic_fields_and_preserves_exact_action_links(self):
        html = self.message()
        parsed = Links()
        parsed.feed(html)
        self.assertEqual(
            parsed.links, ['https://crm.example.test/crm#invite=demo:token&test=1'] * 2
        )
        self.assertNotIn('script', parsed.tags)
        self.assertNotIn('img', parsed.tags)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('Orvia CRM', html)
        self.assertIn('lang="fr"', html)
        self.assertNotIn('<link ', html)

    def test_unsafe_action_urls_rejected_and_production_requires_https(self):
        for url in ('javascript:alert(1)', '//host/crm', 'https://user:pass@host/crm'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.message(url=url)
        with override_settings(DEBUG=False):
            with self.assertRaises(ValueError):
                self.message(url='http://crm.example.test/crm')

    def test_html_is_encrypted_multipart_delivered_and_erased_with_queue_payload(self):
        user = get_user_model().objects.create_user('test', email='test@example.test')
        token = default_token_generator.make_token(user)
        html = self.message()
        row = enqueue(
            user=user,
            subject='Orvia CRM',
            body='Texte de secours',
            html=html,
            recipient=user.email,
            guard={'kind': 'recovery', 'user': user.pk, 'token': token},
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        self.assertNotIn('demo:token', row.payload)
        self.assertNotIn('<html', row.payload)
        self.assertEqual(dispatch()['sent'], 1)
        sent = mail.outbox[-1]
        self.assertEqual(sent.body, 'Texte de secours')
        self.assertEqual(sent.alternatives[0][0], html)
        self.assertEqual(sent.alternatives[0][1], 'text/html')
        row.refresh_from_db()
        self.assertEqual(row.payload, '')

    def test_preexisting_text_only_payload_is_still_delivered(self):
        user = get_user_model().objects.create_user('legacy', email='legacy@example.test')
        token = default_token_generator.make_token(user)
        row = enqueue(
            user=user,
            subject='Ancien',
            body='Texte existant',
            recipient=user.email,
            guard={'kind': 'recovery', 'user': user.pk, 'token': token},
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        payload = json.loads(cipher().decrypt(row.payload.encode()))
        del payload['html']
        PortalMail.objects.filter(pk=row.pk).update(
            payload=cipher().encrypt(json.dumps(payload).encode()).decode()
        )
        self.assertEqual(dispatch()['sent'], 1)
        self.assertEqual(mail.outbox[-1].body, 'Texte existant')
        self.assertEqual(mail.outbox[-1].alternatives, [])
