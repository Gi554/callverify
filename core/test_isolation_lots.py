import uuid
from datetime import timedelta
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue
from packages.access.isolation import issue_lot
from .models import AdminUser, AuditEvent, Campaign, Prospect


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class IsolationLotTests(TestCase):
    def setUp(self):
        cache.clear()
        owner = AdminUser.objects.create_user('legacy-admin', is_staff=True)
        campaign = Campaign.objects.create(
            owner=owner, name='Isolation', purpose='Test', source='Fictif'
        )
        self.rows = [
            Prospect.objects.create(campaign=campaign, name=f'P{n}', raw_phone=f'416555{n:04d}')
            for n in range(5)
        ]
        self.client = APIClient()
        self.base = '/api/work-queue/lots/'

    def auth(self, pk, role):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(pk, 'isolation', role))

    def assign(self, count, setter=21, request_id=None, actor=91):
        self.auth(91, 'administrator')
        return self.client.post(
            self.base + 'assign/',
            {
                'request_id': str(request_id or uuid.uuid4()),
                'proof': issue_lot(actor, setter, 'Setter Un'),
                'count': count,
            },
            format='json',
        )

    def test_lot_goes_to_the_attested_setter_and_stamps_the_week(self):
        response = self.assign(3)
        self.assertEqual((response.status_code, response.data['assigned']), (201, 3))
        mine = Prospect.objects.filter(assigned_setter_id=21)
        self.assertEqual(mine.count(), 3)
        row = mine.first()
        today = timezone.localdate()
        self.assertEqual(row.lot_week, today - timedelta(days=today.weekday()))
        self.assertEqual(row.assignment_revision, 1)
        self.assertEqual(row.assigned_setter_name, 'Setter Un')
        self.assertEqual(AuditEvent.objects.filter(action='isolation.lot.assigned').count(), 1)

    def test_replay_assigns_once_and_reused_id_with_other_count_conflicts(self):
        request_id = uuid.uuid4()
        self.assertEqual(self.assign(2, request_id=request_id).data['assigned'], 2)
        replay = self.assign(2, request_id=request_id)
        self.assertEqual((replay.data['assigned'], replay.data['replayed']), (2, True))
        self.assertEqual(self.assign(4, request_id=request_id).status_code, 409)
        self.assertEqual(Prospect.objects.filter(assigned_setter_id=21).count(), 2)

    def test_only_unassigned_active_prospects_are_given(self):
        Prospect.objects.filter(pk=self.rows[0].pk).update(assigned_setter_id=30)
        Prospect.objects.filter(pk=self.rows[1].pk).update(commercial_status='not_interested')
        self.assertEqual(self.assign(10).data['assigned'], 3)
        self.assertEqual(
            set(Prospect.objects.filter(assigned_setter_id=21).values_list('pk', flat=True)),
            {row.pk for row in self.rows[2:]},
        )

    def test_summary_lists_free_prospects_and_each_setters_lot(self):
        self.assign(2)
        self.auth(91, 'administrator')
        data = self.client.get(self.base).data
        self.assertEqual(data['available'], 3)
        self.assertEqual([(row['id'], row['assigned']) for row in data['setters']], [(21, 2)])

    def test_release_only_returns_untouched_prospects(self):
        self.assign(3)
        Prospect.objects.filter(pk=self.rows[0].pk).update(commercial_status='callback')
        self.auth(91, 'administrator')
        response = self.client.post(
            self.base + 'release/',
            {'request_id': str(uuid.uuid4()), 'setter_id': 21},
            format='json',
        )
        self.assertEqual(response.data['released'], 2)
        self.assertEqual(Prospect.objects.filter(assigned_setter_id=21).count(), 1)
        self.assertEqual(Prospect.objects.filter(assigned_setter_id__isnull=True).count(), 4)

    def test_setters_proofs_of_other_actors_and_other_roles_are_refused(self):
        self.assertEqual(self.assign(1, actor=92).status_code, 400)
        self.auth(21, 'setter')
        self.assertEqual(self.client.get(self.base).status_code, 403)
        self.assertEqual(
            self.client.post(
                self.base + 'assign/',
                {
                    'request_id': str(uuid.uuid4()),
                    'proof': issue_lot(21, 21, 'Setter Un'),
                    'count': 1,
                },
                format='json',
            ).status_code,
            403,
        )
        self.assertEqual(Prospect.objects.filter(assigned_setter_id__isnull=False).count(), 0)

    def test_owner_me_lists_only_the_prospects_given_to_the_caller(self):
        self.assign(2, setter=91)
        self.auth(91, 'administrator')
        self.assertEqual(self.client.get('/api/work-queue/?owner=me').data['count'], 2)
        self.assertEqual(self.client.get('/api/work-queue/').data['count'], 5)
        self.auth(21, 'setter')
        self.assertEqual(self.client.get('/api/work-queue/?owner=me').data['count'], 0)
