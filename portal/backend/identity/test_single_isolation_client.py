from io import StringIO
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.management import call_command,CommandError
from django.db import IntegrityError,transaction
from django.test import TestCase,override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from .models import Membership,Invitation
from .invitations import digest

@override_settings(DEBUG=True,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SingleClientTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_user('admin')
        for space in ('isolation','assurance'):Membership.objects.create(user=self.admin,workspace=space,role='administrator')
        self.owner=get_user_model().objects.create_user('unique-client')
        self.client_access=Membership.objects.create(user=self.owner,workspace='isolation',role='client')
        self.other=get_user_model().objects.create_user('other')
        self.client=APIClient();self.client.force_authenticate(self.admin)
        self.url='/api/portal/workspaces/isolation/users/'
    def test_database_rejects_second_client_even_if_inactive(self):
        self.client_access.active=False;self.client_access.save()
        for active in (True,False):
            with self.assertRaises(IntegrityError),transaction.atomic():Membership.objects.create(user=self.other,workspace='isolation',role='client',active=active)
    def test_creation_and_role_promotion_refused_without_orphan_accounts(self):
        count=get_user_model().objects.count()
        response=self.client.post(self.url,{'username':'second','password':'Synthetic-Strong!4827','role':'client'},format='json')
        self.assertEqual(response.status_code,400);self.assertEqual(get_user_model().objects.count(),count)
        setter=Membership.objects.create(user=self.other,workspace='isolation',role='setter')
        self.assertEqual(self.client.patch(self.url+str(setter.pk)+'/',{'role':'client'},format='json').status_code,400)
        setter.refresh_from_db();self.assertEqual(setter.role,'setter')
    def test_suspend_reactivate_but_no_repurpose_of_client_slot(self):
        url=self.url+str(self.client_access.pk)+'/'
        self.assertEqual(self.client.patch(url,{'active':False},format='json').status_code,200)
        self.assertEqual(self.client.patch(url,{'role':'setter'},format='json').status_code,400)
        self.assertEqual(self.client.patch(url,{'active':True},format='json').status_code,200)
        self.client_access.refresh_from_db();self.assertEqual(self.client_access.role,'client');self.assertTrue(self.client_access.active)
    def test_assurance_advisors_remain_multiple_and_independent(self):
        for user in (self.owner,self.other):Membership.objects.create(user=user,workspace='assurance',role='advisor')
        self.assertEqual(Membership.objects.filter(workspace='assurance',role='advisor').count(),2)
    def test_invitation_creation_resend_and_acceptance_cannot_add_second_client(self):
        url='/api/portal/workspaces/isolation/invitations/'
        response=self.client.post(url,{'username':'invited','email':'invited@example.invalid','role':'client'},format='json')
        self.assertEqual(response.status_code,400);self.assertFalse(Invitation.objects.exists())
        # A legacy invitation may predate the single-client configuration.
        invitation=Invitation.objects.create(username='legacy-invited',email='legacy@example.invalid',workspace='isolation',role='client',issuer=self.admin,token_hash=digest('synthetic-token'),expires_at=timezone.now()+timedelta(hours=24))
        self.assertEqual(self.client.post(url+str(invitation.pk)+'/',{'action':'resend'},format='json').status_code,400)
        public=APIClient()
        response=public.post('/api/portal/invitations/accept/',{'id':str(invitation.pk),'token':'synthetic-token','password':'Synthetic-Strong!4827','confirmation':'Synthetic-Strong!4827'},format='json')
        self.assertEqual(response.status_code,400)
        self.assertFalse(get_user_model().objects.filter(username='legacy-invited').exists())
        invitation.refresh_from_db();self.assertIsNone(invitation.accepted_at)
        self.assertEqual(self.client.post(url+str(invitation.pk)+'/',{'action':'revoke'},format='json').status_code,200)
    def test_management_command_cannot_replace_or_demote_client(self):
        for username,role in ((self.other.username,'client'),(self.owner.username,'setter')):
            with self.assertRaises(CommandError):call_command('grant_workspace',username,'isolation',role,stdout=StringIO())
        self.client_access.active=False;self.client_access.save()
        call_command('grant_workspace',self.owner.username,'isolation','client',stdout=StringIO())
        self.client_access.refresh_from_db();self.assertTrue(self.client_access.active)

    def test_migration_refuses_existing_duplicates_without_deletion(self):
        from importlib import import_module
        from unittest.mock import Mock
        module=import_module('portal.backend.identity.migrations.0014_membership_single_isolation_client')
        apps=Mock();editor=Mock();editor.connection.alias='default'
        model=apps.get_model.return_value
        model.objects.using.return_value.filter.return_value.count.return_value=2
        with self.assertRaisesRegex(RuntimeError,'aucune donnée'):module.check_existing(apps,editor)
        model.objects.using.return_value.filter.return_value.delete.assert_not_called()
