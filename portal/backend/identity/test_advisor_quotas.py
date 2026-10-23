from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from .models import Membership, Invitation, AccessAudit
from .test_invitations import InvitationTests


@override_settings(
    DEBUG=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PORTAL_PUBLIC_URL='http://localhost:5173',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class AdvisorQuotaTests(TestCase):
    setUp = InvitationTests.setUp
    create = InvitationTests.create
    payload = InvitationTests.payload
    accept = InvitationTests.accept

    def grant(self, **values):
        return self.client.post(
            '/api/portal/workspaces/assurance/users/',
            {'password': 'Initial-Password!6241', **values},
            format='json',
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def patch(self, pk, values):
        return self.client.patch(
            f'/api/portal/workspaces/assurance/users/{pk}/',
            values,
            format='json',
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def test_invitation_quota_reaches_the_advisor_membership(self):
        self.assertEqual(self.create(prospect_quota=40).status_code, 201)
        self.assertEqual(Invitation.objects.get().prospect_quota, 40)
        self.assertEqual(self.accept(self.payload()).status_code, 204)
        row = Membership.objects.get(user__username='newperson')
        self.assertEqual(row.prospect_quota, 40)
        audit = AccessAudit.objects.get(action='invitation.created')
        self.assertEqual(audit.metadata['prospect_quota'], 40)

    def test_quota_is_reserved_to_advisors_and_bounded(self):
        response = self.create(role='setter', prospect_quota=10)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.create(prospect_quota=0).status_code, 400)
        self.assertEqual(self.create(prospect_quota=100001).status_code, 400)
        self.assertEqual(
            self.grant(username='setter-q', role='setter', prospect_quota=5).status_code, 400
        )

    def test_created_advisor_quota_can_be_edited_and_is_dropped_with_the_role(self):
        response = self.grant(username='advisor-q', role='advisor', prospect_quota=25)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['prospect_quota'], 25)
        pk = response.data['id']
        self.assertEqual(self.patch(pk, {'prospect_quota': 30}).data['prospect_quota'], 30)
        self.assertEqual(self.patch(pk, {'prospect_quota': None}).data['prospect_quota'], None)
        self.patch(pk, {'prospect_quota': 12})
        changed = self.patch(pk, {'role': 'setter'})
        self.assertEqual(changed.status_code, 200)
        self.assertIsNone(changed.data['prospect_quota'])
        self.assertEqual(self.patch(pk, {'prospect_quota': 3}).status_code, 400)
        audit = AccessAudit.objects.filter(action='membership.updated').last()
        self.assertEqual(audit.metadata['before']['prospect_quota'], 12)

    def test_every_assurance_member_reads_the_quotas(self):
        self.grant(username='advisor-a', role='advisor', prospect_quota=20)
        self.grant(username='advisor-b', role='advisor')
        setter = get_user_model().objects.create_user('setter-read')
        Membership.objects.create(user=setter, workspace='assurance', role='setter')
        outsider = get_user_model().objects.create_user('outsider')
        Membership.objects.create(user=outsider, workspace='isolation', role='setter')
        reader = APIClient()
        reader.force_login(setter)
        response = reader.get('/api/portal/assurance/advisor-quotas/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(
            [(row['name'], row['quota']) for row in response.data['results']],
            [('advisor-a', 20), ('advisor-b', None)],
        )
        reader.force_login(outsider)
        self.assertEqual(reader.get('/api/portal/assurance/advisor-quotas/').status_code, 403)
