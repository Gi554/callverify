from datetime import timedelta,datetime,time,timezone as utc
from zoneinfo import ZoneInfo
from unittest.mock import patch,Mock
from django.contrib.auth import get_user_model
from django.test import TestCase,override_settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.phone_history import issue,verify
from packages.access.phone_calls import verify as verify_call
from packages.newt.directory import DirectoryUnavailable
from .models import Membership,PhoneExtension,AccessAudit,PhoneCallAttempt
from .phone_history import eligible


@override_settings(DEBUG=True,NEWT_CDR_HISTORY_ENABLED=True,NEWT_USERNAME='synthetic',NEWT_PASSWORD='secret')
class PhoneHistoryTests(TestCase):
    def setUp(self):
        cache.clear();self.user=get_user_model().objects.create_user('setter')
        self.memberships=[Membership.objects.create(user=self.user,workspace=space,role='setter') for space in ('assurance','isolation')]
        self.link=PhoneExtension.objects.create(user=self.user,extension='501')
        self.day=timezone.now().astimezone(ZoneInfo('America/Toronto')).date()-timedelta(days=1)
        PhoneExtension.objects.filter(pk=self.link.pk).update(updated_at=timezone.now()-timedelta(days=3))
        self.client=APIClient();self.client.force_login(self.user)
        self.url='/api/portal/isolation/phone-history/'
        self.body={'proof':issue(self.user.pk,42,0,'15145550100','isolation'),'starts_on':str(self.day),'ends_on':str(self.day)}
        self.check=patch('portal.backend.identity.phone_history.eligible',return_value=True).start();self.addCleanup(patch.stopall)
        self.fetch=patch('portal.backend.identity.phone_history.fetch_records',return_value=[self.row()]).start()
    def row(self,**changes):
        instant=datetime.combine(self.day,time(10),ZoneInfo('America/Toronto')).astimezone(utc.utc)
        return {'from':'501','to':'5145550100','description':'SECRET CITY','dnid':'SECRET DNID',
            'local_date':str(self.day),'local_time':'10:00:00','timezone':'America/Toronto','occurred_at':instant.isoformat(),
            'duration_raw':'8','amount_raw':'SECRET AMOUNT',**changes}
    def post(self,**changes):return self.client.post(self.url,{**self.body,**changes},format='json')

    def test_scopes_to_current_post_number_and_filters_before_pagination(self):
        self.fetch.return_value=[self.row() for _ in range(27)]+[self.row(**{'from':'999'}),self.row(to='5145550101'),self.row(occurred_at=None)]
        first=self.post();self.assertEqual(first.status_code,200,first.data)
        self.assertEqual(first.data['count'],27);self.assertEqual(len(first.data['results']),25)
        self.assertTrue(first.data['has_next'])
        self.assertEqual(len(self.post(page=2).data['results']),2)
        self.assertNotIn('SECRET',str(first.data));self.assertNotIn('15145550100',str(first.data))
        self.assertEqual(first['Cache-Control'],'no-store')
        self.fetch.assert_called_with('synthetic','secret',self.day,self.day)
        self.check.assert_called();self.assertFalse(PhoneCallAttempt.objects.exists())
        audits=str(list(AccessAudit.objects.values('metadata')))
        self.assertNotIn('5145550100',audits);self.assertNotIn('SECRET',audits)

    def test_records_before_association_outside_window_and_ambiguous_dates_are_excluded(self):
        self.fetch.return_value=[self.row(occurred_at=(timezone.now()-timedelta(days=10)).isoformat()),
            self.row(local_date=str(self.day-timedelta(days=1))),self.row(occurred_at=None)]
        response=self.post();self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['count'],0)
        self.assertIn('ne prouve pas',response.data['definition'])

    def test_business_preflight_must_pass_twice_and_revocation_discards_results(self):
        self.check.return_value=False
        self.assertEqual(self.post().status_code,403);self.fetch.assert_not_called()
        self.check.side_effect=[True,False]
        response=self.post();self.assertEqual(response.status_code,403)
        self.assertNotIn('SECRET',str(response.data));self.assertFalse(AccessAudit.objects.exists())

    def test_wrong_actor_workspace_call_proof_expiry_and_extra_fields_fail_without_fetch(self):
        for proof in (issue(self.user.pk+1,42,0,'15145550100','isolation'),issue(self.user.pk,42,0,'15145550100','assurance'),'invalid'):
            self.assertEqual(self.post(proof=proof).status_code,400)
        self.assertEqual(self.post(extension='999').status_code,400)
        self.assertEqual(self.client.post(self.url+'?_f=245',self.body,format='json').status_code,400)
        with patch('django.core.signing.time.time',return_value=timezone.now().timestamp()+61):self.assertEqual(self.post().status_code,400)
        self.fetch.assert_not_called()
        from django.core import signing
        with self.assertRaises(signing.BadSignature):verify_call(self.body['proof'],self.user.pk,'isolation')

    def test_disabled_unconfigured_role_and_missing_link_fail_without_provider(self):
        with override_settings(NEWT_CDR_HISTORY_ENABLED=False):self.assertEqual(self.post().status_code,503)
        with override_settings(NEWT_PASSWORD=''):self.assertEqual(self.post().status_code,503)
        PhoneExtension.objects.filter(pk=self.link.pk).update(extension=None)
        self.assertEqual(self.post().status_code,400)
        for role in ('client','closer','administrator'):
            cache.clear()
            Membership.objects.filter(workspace='isolation').update(role=role)
            self.assertEqual(self.post().status_code,403)
        self.fetch.assert_not_called()

    def test_invalid_window_page_and_get_rejected(self):
        for changes in ({'starts_on':'bad'},{'starts_on':str(self.day-timedelta(days=7))},
                        {'ends_on':str(self.day+timedelta(days=2))},{'page':0}):
            self.assertEqual(self.post(**changes).status_code,400,changes)
        self.assertEqual(self.client.get(self.url).status_code,405);self.fetch.assert_not_called()

    def test_provider_failure_is_not_empty_success_or_raw_leak(self):
        self.fetch.side_effect=DirectoryUnavailable('SECRET RAW CDR')
        response=self.post();self.assertEqual(response.status_code,503)
        self.assertNotIn('SECRET',str(response.data));self.assertFalse(AccessAudit.objects.exists())

    def test_assurance_same_contract_and_csrf(self):
        self.url='/api/portal/assurance/phone-history/'
        self.body['proof']=issue(self.user.pk,42,0,'15145550100','assurance')
        self.assertEqual(self.post().status_code,200)
        client=APIClient(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post(self.url,self.body,format='json').status_code,403)

    def test_preflight_fixed_endpoint_authenticated_bounded_and_fail_closed(self):
        # Call the actual function directly, not the mocked module attribute.
        response=Mock(status_code=200);response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.raw.read.return_value=b'{"eligible":true}'
        claims=verify(self.body['proof'],self.user.pk,'isolation')
        with patch('portal.backend.identity.phone_history.requests.post',return_value=response) as http:
            self.assertTrue(eligible(self.user,'isolation',claims,self.body['proof']))
            self.assertTrue(http.call_args.args[0].endswith('/api/work-queue/42/phone-history-check/'))
            self.assertFalse(http.call_args.kwargs['allow_redirects'])
            self.assertTrue(http.call_args.kwargs['headers']['Authorization'].startswith('Bearer '))
            response.raw.read.return_value=b'x'*1025
            self.assertFalse(eligible(self.user,'isolation',claims,self.body['proof']))
