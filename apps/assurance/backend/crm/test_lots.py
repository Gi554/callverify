import uuid
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from packages.access.followups import issue_lot
from packages.access.tickets import issue
from .models import BusinessAudit, Contact, ContactImport


@override_settings(DEBUG=True)
class LotTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.contacts = [
            Contact.objects.create(name=f'Prospect {n}', phone=f'0{n}', created_by_id=1)
            for n in range(5)
        ]

    def auth(self, pk, role):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(pk, 'assurance', role))

    def give(self, count, setter=21, request_id=None, actor=1, **extra):
        self.auth(1, 'administrator')
        return self.client.post(
            '/api/assurance/lots/',
            {
                'request_id': str(request_id or uuid.uuid4()),
                'proof': issue_lot(actor, setter, 'Setter Un'),
                'count': count,
                **extra,
            },
            format='json',
        )

    def test_setters_share_the_pool_until_the_first_lot_is_given(self):
        self.auth(21, 'setter')
        self.assertEqual(self.client.get('/api/assurance/contacts/').json()['count'], 5)
        self.auth(22, 'setter')
        self.assertEqual(self.client.get('/api/assurance/contacts/').json()['count'], 5)

    def test_setter_only_sees_the_lot_given_by_the_administrator(self):
        response = self.give(2)
        self.assertEqual((response.status_code, response.json()['assigned']), (201, 2))
        self.auth(21, 'setter')
        rows = self.client.get('/api/assurance/contacts/').json()['results']
        names = [row['name'] for row in rows]
        self.assertEqual(sorted(names), ['Prospect 0', 'Prospect 1'])
        self.auth(22, 'setter')
        self.assertEqual(self.client.get('/api/assurance/contacts/').json()['count'], 0)
        self.auth(1, 'administrator')
        self.assertEqual(self.client.get('/api/assurance/contacts/').json()['count'], 5)

    def test_summary_counts_free_and_assigned_prospects(self):
        self.give(2)
        self.auth(1, 'administrator')
        data = self.client.get('/api/assurance/lots/').json()
        self.assertEqual(data['available'], 3)
        self.assertEqual(data['setters'], [{'id': 21, 'name': 'Setter Un', 'assigned': 2}])

    def test_replay_does_not_assign_twice(self):
        request_id = uuid.uuid4()
        self.assertEqual(self.give(2, request_id=request_id).json()['assigned'], 2)
        replay = self.give(2, request_id=request_id).json()
        self.assertEqual((replay['assigned'], replay['replayed']), (2, True))
        self.assertEqual(Contact.objects.filter(assigned_setter_id=21).count(), 2)

    def test_lot_can_be_limited_to_one_import_and_skips_processed_prospects(self):
        batch = ContactImport.objects.create(
            request_id=uuid.uuid4(),
            fingerprint='f',
            filename='liste.csv',
            created_by_id=1,
            total=2,
            imported=2,
            rejected=0,
        )
        Contact.objects.filter(pk__in=[self.contacts[3].pk, self.contacts[4].pk]).update(
            import_batch=batch
        )
        Contact.objects.filter(pk=self.contacts[3].pk).update(status='callback')
        response = self.give(10, import_id=batch.pk)
        self.assertEqual(response.json()['assigned'], 2)
        self.assertEqual(
            set(Contact.objects.filter(assigned_setter_id=21).values_list('pk', flat=True)),
            {self.contacts[3].pk, self.contacts[4].pk},
        )

    def test_proof_of_another_actor_and_non_admin_are_refused(self):
        self.assertEqual(self.give(1, actor=2).status_code, 400)
        self.auth(21, 'setter')
        self.assertEqual(self.client.get('/api/assurance/lots/').status_code, 403)
        self.assertEqual(
            self.client.post(
                '/api/assurance/lots/',
                {
                    'request_id': str(uuid.uuid4()),
                    'proof': issue_lot(21, 21, 'Setter Un'),
                    'count': 1,
                },
                format='json',
            ).status_code,
            403,
        )
        self.assertEqual(Contact.objects.filter(assigned_setter_id__isnull=False).count(), 0)

    def test_release_gives_back_untouched_prospects_only(self):
        self.give(3)
        Contact.objects.filter(pk=self.contacts[0].pk).update(lease_owner_id=21)
        self.auth(1, 'administrator')
        response = self.client.post(
            '/api/assurance/lots/release/',
            {'request_id': str(uuid.uuid4()), 'setter_id': 21},
            format='json',
        )
        self.assertEqual(response.json()['released'], 2)
        self.assertEqual(Contact.objects.filter(assigned_setter_id=21).count(), 1)
        self.assertEqual(
            list(BusinessAudit.objects.order_by('pk').values_list('action', flat=True)),
            ['lot.assigned', 'lot.released'],
        )
