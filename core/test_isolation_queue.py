from datetime import timedelta
from uuid import uuid4
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .test_isolation_work import fixture
from .models import Prospect, IsolationVisit


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class IsolationQueueTests(TestCase):
    def test_active_queue_keeps_history_and_assignment_scope(self):
        first = fixture()
        first.assigned_setter_id = 21
        first.save()
        declined = Prospect.objects.create(
            campaign=first.campaign,
            raw_phone='5145550102',
            name='Declined synthetic',
            assigned_setter_id=21,
            commercial_status='not_interested',
        )
        booked = Prospect.objects.create(
            campaign=first.campaign,
            raw_phone='5145550103',
            name='Booked synthetic',
            assigned_setter_id=21,
        )
        IsolationVisit.objects.create(
            prospect=booked,
            request_id=uuid4(),
            fingerprint='test',
            client_id=41,
            client_name='Client',
            setter_id=21,
            setter_name='Setter',
            booked_by_id=21,
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=1),
            timezone='UTC',
        )
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(21, 'isolation', 'setter'))
        result = client.get('/api/work-queue/', {'queue': 'active'})
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual([row['id'] for row in result.data['results']], [first.pk])
        result = client.get('/api/work-queue/', {'queue': 'all'})
        self.assertEqual(
            {row['id']: row['queue_reason'] for row in result.data['results']},
            {first.pk: '', declined.pk: 'not_interested', booked.pk: 'appointment_booked'},
        )
        self.assertEqual(client.get(f'/api/work-queue/{declined.pk}/').status_code, 200)
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(22, 'isolation', 'setter'))
        self.assertEqual(client.get('/api/work-queue/', {'queue': 'all'}).data['count'], 0)
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + issue(91, 'isolation', 'administrator'))
        self.assertEqual(client.get('/api/work-queue/', {'queue': 'all'}).data['count'], 3)
        self.assertEqual(client.get('/api/work-queue/', {'queue': 'bad'}).status_code, 400)
