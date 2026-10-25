from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from django.core import signing
from django.conf import settings
from unittest import skipUnless

if 'portal.backend.identity' in settings.INSTALLED_APPS:
    from .models import Membership
from packages.access.tickets import issue, verify


@override_settings(DEBUG=True, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
@skipUnless(settings.ROOT_URLCONF == 'portal.backend.urls', 'Service portail indépendant')
class PortalTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('test', password='long-test-password')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_single_workspace_landing_and_denied_other(self):
        Membership.objects.create(user=self.user, workspace='isolation', role='setter')
        self.assertEqual(self.client.get('/api/portal/session/').data['landing'], 'isolation')
        self.assertEqual(self.client.post('/api/portal/access/assurance/').status_code, 403)

    def test_multi_workspace_requires_choice(self):
        for space in ('assurance', 'isolation'):
            Membership.objects.create(user=self.user, workspace=space, role='administrator')
        self.assertIsNone(self.client.get('/api/portal/session/').data['landing'])

    def test_revoked_membership_does_not_issue_ticket(self):
        Membership.objects.create(
            user=self.user, workspace='assurance', role='advisor', active=False
        )
        self.assertEqual(self.client.post('/api/portal/access/assurance/').status_code, 403)

    def test_audience_and_signature_are_checked(self):
        token = issue(self.user.pk, 'isolation', 'administrator')
        with self.assertRaises(signing.BadSignature):
            verify(token, 'assurance')
        with self.assertRaises(signing.BadSignature):
            verify(token + 'x', 'isolation')

    def test_no_membership_even_for_central_superuser(self):
        self.user.is_superuser = True
        self.user.save()
        self.assertEqual(self.client.post('/api/portal/access/assurance/').status_code, 403)

    def test_login_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertEqual(
            client.post(
                '/api/portal/login/',
                {'username': 'test', 'password': 'long-test-password'},
                format='json',
            ).status_code,
            403,
        )

    def test_expired_ticket_is_rejected(self):
        from unittest.mock import patch

        with patch('django.core.signing.time.time', return_value=1000):
            token = issue(self.user.pk, 'assurance', 'advisor')
        with self.assertRaises(signing.SignatureExpired):
            verify(token, 'assurance')


@override_settings(DEBUG=True, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
@skipUnless(settings.ROOT_URLCONF == 'portal.backend.urls', 'Service portail indépendant')
class AccessManagementTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user('manager', password='strong-password-42')
        self.own = Membership.objects.create(
            user=self.actor, workspace='assurance', role='administrator'
        )
        self.other = get_user_model().objects.create_user('target', password='unchanged-password')
        self.target = Membership.objects.create(
            user=self.other, workspace='assurance', role='setter'
        )
        self.isolation = Membership.objects.create(
            user=self.other, workspace='isolation', role='client'
        )
        self.client = APIClient()
        self.client.force_authenticate(self.actor)
        self.url = '/api/portal/workspaces/assurance/users/'

    def test_scope_and_no_implicit_superuser(self):
        self.assertEqual(
            self.client.get('/api/portal/workspaces/isolation/users/').status_code, 403
        )
        self.actor.is_superuser = True
        self.actor.save()
        self.own.delete()
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_list_excludes_other_workspace_and_secrets(self):
        data = self.client.get(self.url).data
        self.assertEqual(data['count'], 2)
        self.assertNotIn('password', str(data))
        self.assertNotIn('client', str(data))
        self.assertEqual(self.client.get(self.url + '?search=target').data['count'], 1)

    def test_create_hashes_password_and_audits_without_secret(self):
        from .models import AccessAudit

        secret = 'Unique-strong-pass-936!'
        response = self.client.post(
            self.url,
            {'username': 'newperson', 'role': 'advisor', 'password': secret},
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(get_user_model().objects.get(username='newperson').check_password(secret))
        self.assertNotIn(secret, str(response.data))
        self.assertNotIn(secret, str(AccessAudit.objects.last().metadata))

    def test_weak_password_and_incompatible_role_do_not_create_user(self):
        for values in (
            {'role': 'advisor', 'password': 'short'},
            {'role': 'client', 'password': 'Unique-strong-pass-936!'},
        ):
            response = self.client.post(self.url, {'username': 'rejected', **values}, format='json')
            self.assertEqual(response.status_code, 400)
        self.assertFalse(get_user_model().objects.filter(username='rejected').exists())

    def test_existing_link_keeps_account_and_other_access(self):
        self.target.delete()
        original = self.other.password
        response = self.client.post(
            self.url, {'username': 'target', 'role': 'advisor', 'existing': True}, format='json'
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.other.refresh_from_db()
        self.isolation.refresh_from_db()
        self.assertEqual(self.other.password, original)
        self.assertEqual(self.isolation.role, 'client')

    def test_self_change_and_cross_workspace_are_blocked(self):
        self.assertEqual(
            self.client.patch(
                self.url + str(self.own.pk) + '/', {'active': False}, format='json'
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.patch(
                self.url + str(self.isolation.pk) + '/', {'active': False}, format='json'
            ).status_code,
            404,
        )

    def test_suspend_only_selected_workspace_and_records_history(self):
        from .models import AccessAudit

        response = self.client.patch(
            self.url + str(self.target.pk) + '/',
            {'active': False, 'role': 'advisor'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.isolation.refresh_from_db()
        self.other.refresh_from_db()
        self.assertTrue(self.isolation.active)
        self.assertTrue(self.other.is_active)
        self.assertEqual(AccessAudit.objects.last().metadata['before']['role'], 'setter')
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post('/api/portal/access/assurance/').status_code, 403)
        self.assertEqual(self.client.post('/api/portal/access/isolation/').status_code, 200)

    def test_session_mutation_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.actor)
        self.assertEqual(
            client.patch(
                self.url + str(self.target.pk) + '/', {'active': False}, format='json'
            ).status_code,
            403,
        )


@override_settings(DEBUG=True, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
@skipUnless(settings.ROOT_URLCONF == 'portal.backend.urls', 'Service portail indépendant')
class ParticipantTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user('assign-manager')
        Membership.objects.create(user=self.actor, workspace='assurance', role='administrator')
        self.setter = get_user_model().objects.create_user('setter-one')
        self.advisor = get_user_model().objects.create_user('advisor-one')
        self.setter_access = Membership.objects.create(
            user=self.setter, workspace='assurance', role='setter'
        )
        self.advisor_access = Membership.objects.create(
            user=self.advisor, workspace='assurance', role='advisor'
        )
        self.client = APIClient()
        self.client.force_authenticate(self.actor)
        self.url = '/api/portal/assurance/participants/'

    def pair(self):
        return self.client.post(
            self.url, {'setter_id': self.setter.pk, 'advisor_id': self.advisor.pk}, format='json'
        )

    def test_directory_lists_only_active_assurance_role_and_no_secrets(self):
        other = get_user_model().objects.create_user('isolation-setter')
        Membership.objects.create(user=other, workspace='isolation', role='setter')
        result = self.client.get(self.url + '?role=setter').data
        self.assertEqual(result['count'], 1)
        self.assertEqual(
            result['results'], [{'id': self.setter.pk, 'name': 'setter-one', 'role': 'setter'}]
        )
        self.assertEqual(self.client.get(self.url + '?role=setter&search=advisor').data['count'], 0)
        # Administrators are listed so that they can take a lot for themselves; nothing else.
        admins = self.client.get(self.url + '?role=administrator')
        self.assertEqual(admins.status_code, 200)
        self.assertTrue(all(set(row) == {'id', 'name', 'role'} for row in admins.data['results']))
        self.assertEqual(self.client.get(self.url + '?role=client').status_code, 400)

    def test_proof_is_bound_to_actor_pair_and_separate_from_login(self):
        from packages.access.assignments import verify_assignment

        response = self.pair()
        self.assertEqual(response.status_code, 200, response.data)
        token = response.data['proof']
        claims = verify_assignment(token, self.actor.pk)
        self.assertEqual(claims['setter']['id'], self.setter.pk)
        with self.assertRaises(signing.BadSignature):
            verify_assignment(token, self.actor.pk + 100)
        with self.assertRaises(signing.BadSignature):
            verify(token, 'assurance')
        with self.assertRaises(signing.BadSignature):
            verify_assignment(issue(self.actor.pk, 'assurance', 'administrator'), self.actor.pk)

    def test_inactive_membership_or_account_cannot_be_attested(self):
        self.advisor_access.active = False
        self.advisor_access.save()
        self.assertEqual(self.pair().status_code, 400)
        self.advisor_access.active = True
        self.advisor_access.save()
        self.advisor.is_active = False
        self.advisor.save()
        self.assertEqual(self.pair().status_code, 400)
        self.assertEqual(self.client.get(self.url + '?role=advisor').data['count'], 0)

    def test_role_change_prevents_new_attestation(self):
        self.advisor_access.role = 'setter'
        self.advisor_access.save()
        self.assertEqual(self.pair().status_code, 400)

    def test_other_roles_and_other_workspace_admin_have_no_directory(self):
        for user in (self.setter, self.advisor):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(self.url + '?role=setter').status_code, 403)
            self.assertEqual(self.pair().status_code, 403)
        Membership.objects.filter(user=self.actor).update(workspace='isolation')
        self.client.force_authenticate(self.actor)
        self.assertEqual(self.pair().status_code, 403)

    def test_proof_expires_after_two_minutes(self):
        from packages.access.assignments import verify_assignment
        from unittest.mock import patch

        with patch('django.core.signing.time.time', return_value=1000):
            token = self.pair().data['proof']
        with self.assertRaises(signing.SignatureExpired):
            verify_assignment(token, self.actor.pk)

    def test_attestation_session_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.actor)
        self.assertEqual(
            client.post(
                self.url,
                {'setter_id': self.setter.pk, 'advisor_id': self.advisor.pk},
                format='json',
            ).status_code,
            403,
        )


@override_settings(DEBUG=True, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
@skipUnless(settings.ROOT_URLCONF == 'portal.backend.urls', 'Service portail indépendant')
class BookingProofTests(TestCase):
    def setUp(self):
        self.setter = get_user_model().objects.create_user('booking-setter')
        self.advisor = get_user_model().objects.create_user('booking-advisor')
        self.manager = get_user_model().objects.create_user('booking-manager')
        Membership.objects.create(user=self.setter, workspace='assurance', role='setter')
        self.advisor_access = Membership.objects.create(
            user=self.advisor, workspace='assurance', role='advisor'
        )
        Membership.objects.create(user=self.manager, workspace='assurance', role='administrator')
        self.client = APIClient()
        self.client.force_authenticate(self.setter)
        self.url = '/api/portal/assurance/booking-proof/'

    def test_setter_can_attest_only_self_without_disclosing_other_setters(self):
        from packages.access.assignments import verify_booking

        response = self.client.post(self.url, {'advisor_id': self.advisor.pk}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            verify_booking(response.data['proof'], self.setter.pk)['setter']['id'], self.setter.pk
        )
        response = self.client.post(
            self.url, {'advisor_id': self.advisor.pk, 'setter_id': self.manager.pk}, format='json'
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_attest_on_behalf_and_proof_is_not_an_assignment_proof(self):
        from packages.access.assignments import verify_booking, verify_assignment

        self.client.force_authenticate(self.manager)
        response = self.client.post(
            self.url, {'setter_id': self.setter.pk, 'advisor_id': self.advisor.pk}, format='json'
        )
        self.assertEqual(response.status_code, 200, response.data)
        proof = response.data['proof']
        self.assertEqual(verify_booking(proof, self.manager.pk)['advisor']['id'], self.advisor.pk)
        with self.assertRaises(signing.BadSignature):
            verify_assignment(proof, self.manager.pk)

    def test_advisor_and_other_workspace_roles_cannot_attest(self):
        self.client.force_authenticate(self.advisor)
        self.assertEqual(
            self.client.post(self.url, {'advisor_id': self.advisor.pk}, format='json').status_code,
            403,
        )
        Membership.objects.filter(user=self.setter).update(workspace='isolation')
        self.client.force_authenticate(self.setter)
        self.assertEqual(
            self.client.post(self.url, {'advisor_id': self.advisor.pk}, format='json').status_code,
            403,
        )

    def test_revoked_or_wrong_role_advisor_is_refused_before_booking(self):
        self.advisor_access.active = False
        self.advisor_access.save()
        self.assertEqual(
            self.client.post(self.url, {'advisor_id': self.advisor.pk}, format='json').status_code,
            400,
        )
        self.advisor_access.active = True
        self.advisor_access.role = 'setter'
        self.advisor_access.save()
        self.assertEqual(
            self.client.post(self.url, {'advisor_id': self.advisor.pk}, format='json').status_code,
            400,
        )

    def test_booking_proof_requires_session_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.setter)
        self.assertEqual(
            client.post(self.url, {'advisor_id': self.advisor.pk}, format='json').status_code, 403
        )
