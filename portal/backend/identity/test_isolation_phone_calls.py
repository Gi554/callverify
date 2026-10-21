from uuid import uuid4
from unittest.mock import patch,Mock
from django.contrib.auth import get_user_model
from django.test import TestCase,override_settings
from rest_framework.test import APIClient
from packages.access.phone_calls import issue,verify
from .models import Membership,PhoneExtension,PhoneCallAttempt
from .phone_calls import eligible

@override_settings(DEBUG=True,NEWT_CALLS_ENABLED=True,NEWT_ISOLATION_CALLS_ENABLED=True,NEWT_USERNAME='test-user',NEWT_PASSWORD='test-secret',ISOLATION_INTERNAL_URL='http://isolation:8000')
class IsolationCallsTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('isolation-setter')
        self.membership=Membership.objects.create(user=self.user,workspace='isolation',role='setter')
        self.client=APIClient();self.client.force_login(self.user);PhoneExtension.objects.create(user=self.user,extension='501')
        self.url='/api/portal/isolation/calls/';self.key=uuid4();self.proof=issue(self.user.pk,12,0,self.key,'14165550123',workspace='isolation')
        checker=patch('portal.backend.identity.phone_calls.eligible',return_value=True);self.checker=checker.start();self.addCleanup(checker.stop)
        provider=patch('portal.backend.identity.phone_calls.place',return_value='accepted');self.provider=provider.start();self.addCleanup(provider.stop)
    def post(self,proof=None):return self.client.post(self.url,{'proof':proof or self.proof},format='json')
    def test_isolation_call_is_one_shot_scoped_and_has_private_status(self):
        result=self.post();self.assertEqual(result.status_code,200,result.data);self.assertEqual(result.data['prospect_id'],12);self.assertEqual(result.data['workspace'],'isolation');self.assertNotIn('contact_id',result.data)
        self.checker.assert_called_once_with(self.user,verify(self.proof,self.user.pk,'isolation'),self.proof,'isolation')
        self.provider.assert_called_once_with('test-user','test-secret','501','14165550123')
        self.assertEqual(self.post().data['state'],'accepted');self.assertEqual(self.provider.call_count,1)
        self.assertEqual(self.client.get(self.url+str(self.key)+'/').status_code,200)
        Membership.objects.create(user=self.user,workspace='assurance',role='setter')
        self.assertEqual(self.client.get('/api/portal/assurance/calls/'+str(self.key)+'/').status_code,404)
        self.assertEqual(PhoneCallAttempt.objects.get().workspace,'isolation')
    def test_wrong_proof_workspace_role_and_disabled_flag_never_send(self):
        assurance=issue(self.user.pk,12,0,uuid4(),'14165550123',uuid4())
        self.assertEqual(self.post(assurance).status_code,400)
        with override_settings(NEWT_ISOLATION_CALLS_ENABLED=False):self.assertEqual(self.post().status_code,503)
        with override_settings(NEWT_CALLS_ENABLED=False):self.assertEqual(self.post().status_code,503)
        for role in ('client','administrator'):
            Membership.objects.filter(pk=self.membership.pk).update(role=role);self.assertEqual(self.post().status_code,403)
        self.provider.assert_not_called()
    def test_preflight_uses_isolation_only_and_checks_exact_response(self):
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False);response.status_code=200;response.raw.read.return_value=b'{"eligible":true}'
        with patch('portal.backend.identity.phone_calls.requests.post',return_value=response) as post:
            self.assertTrue(eligible(self.user,verify(self.proof,self.user.pk,'isolation'),self.proof,'isolation'))
            self.assertEqual(post.call_args.args[0],'http://isolation:8000/api/work-queue/12/call-intent-check/')
            self.assertFalse(post.call_args.kwargs['allow_redirects'])
    def test_ineligible_and_ambiguous_results_are_not_resent(self):
        self.checker.return_value=False
        self.assertEqual(self.post().data['state'],'blocked');self.assertEqual(self.post().data['state'],'blocked');self.provider.assert_not_called()
    def test_cooldown_is_shared_with_assurance_for_the_same_physical_post(self):
        self.post();Membership.objects.create(user=self.user,workspace='assurance',role='setter')
        proof=issue(self.user.pk,42,0,uuid4(),'15145550101',uuid4())
        self.assertEqual(self.client.post('/api/portal/assurance/calls/',{'proof':proof},format='json').status_code,409)
        self.assertEqual(self.provider.call_count,1)

    def test_options_never_send_and_reveal_no_extension(self):
        with override_settings(NEWT_ISOLATION_CALLS_ENABLED=False):
            response=self.client.get(self.url+'options/')
            self.assertEqual(response.status_code,200);self.assertEqual(response.data,{'enabled':False,'post_associated':True})
            self.assertEqual(response['Cache-Control'],'no-store')
        self.assertTrue(self.client.get(self.url+'options/').data['enabled'])
        Membership.objects.filter(pk=self.membership.pk).update(role='client')
        self.assertEqual(self.client.get(self.url+'options/').status_code,403)
        self.provider.assert_not_called()
