from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from .models import Membership


@override_settings(DEBUG=True)
class ActorNamesTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user('admin')
        self.actor = get_user_model().objects.create_user(
            'historic-setter', first_name='Synthetic', last_name='Setter'
        )
        self.foreign = get_user_model().objects.create_user('foreign')
        Membership.objects.create(user=self.admin, workspace='assurance', role='administrator')
        Membership.objects.create(
            user=self.actor, workspace='assurance', role='setter', active=False
        )
        Membership.objects.create(user=self.foreign, workspace='isolation', role='setter')
        self.client = APIClient()
        self.client.force_login(self.admin)
        self.url = '/api/portal/assurance/actor-names/'

    def test_administrator_resolves_historical_members_without_cross_space_leak(self):
        result = self.client.get(self.url, {'ids': f'{self.actor.pk},{self.foreign.pk}'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            result.data, {'results': [{'id': self.actor.pk, 'name': 'Synthetic Setter'}]}
        )
        self.assertEqual(result['Cache-Control'], 'no-store')
        self.assertEqual(
            self.client.get(
                '/api/portal/isolation/actor-names/', {'ids': self.foreign.pk}
            ).status_code,
            403,
        )

    def test_non_admin_and_invalid_queries_are_refused(self):
        for query in (
            {},
            {'ids': 'x'},
            {'ids': ','.join('1' for _ in range(26))},
            {'ids': '1', 'other': 'x'},
        ):
            self.assertEqual(self.client.get(self.url, query).status_code, 400)
        Membership.objects.filter(user=self.admin).update(role='setter')
        self.assertEqual(self.client.get(self.url, {'ids': self.actor.pk}).status_code, 403)
