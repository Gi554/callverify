from datetime import timedelta
from urllib.parse import urlsplit,parse_qs
from unittest import skipUnless
from unittest.mock import patch,Mock
from concurrent.futures import ThreadPoolExecutor
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection,close_old_connections
from django.test import TestCase,TransactionTestCase,override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.calendar_connectors import providers
from .models import Membership,CalendarConnection,CalendarAuthorization,AccessAudit
from .calendars import seal,unseal

OPTIONS={'DEBUG':True,'GOOGLE_CALENDAR_CLIENT_ID':'google-test-id','GOOGLE_CALENDAR_CLIENT_SECRET':'google-test-secret',
    'MICROSOFT_CALENDAR_CLIENT_ID':'ms-test-id','MICROSOFT_CALENDAR_CLIENT_SECRET':'ms-test-secret','MICROSOFT_CALENDAR_TENANT':'common',
    'PORTAL_CALENDAR_KEY':'','PORTAL_PUBLIC_URL':'http://127.0.0.1:5173','PASSWORD_HASHERS':['django.contrib.auth.hashers.MD5PasswordHasher']}
TOKENS={'access':'private-access-test','refresh':'private-refresh-test'}

@override_settings(**OPTIONS)
class CalendarTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user=get_user_model().objects.create_user('advisor',password='strong-test-password')
        self.grant=Membership.objects.create(user=self.user,workspace='assurance',role='advisor')
        self.client=APIClient();self.client.force_login(self.user)
        self.base='/api/portal/calendar/';self.start_url=self.base+'assurance/start/';self.callback_url=self.base+'callback/google/'
        self.window={'starts_at':'2026-12-01T00:00:00-05:00','ends_at':'2026-12-02T00:00:00-05:00'}
    def start(self,provider='google'):
        result=self.client.post(self.start_url,{'provider':provider},format='json');self.assertEqual(result.status_code,200,result.data)
        return parse_qs(urlsplit(result.data['authorization_url']).query)['state'][0]
    def callback(self,state,**changes):return self.client.post(self.callback_url,{'state':state,'code':'single-use-code',**changes},format='json')
    def connected(self):
        state=self.start()
        with patch('packages.calendar_connectors.providers.tokens',return_value=(TOKENS,3600)):self.assertEqual(self.callback(state).status_code,200)
        return CalendarConnection.objects.get()
    def test_owner_roles_only_and_configuration_status(self):
        data=self.client.get(self.base).data['connections'];self.assertEqual(len(data),1);self.assertFalse(data[0]['connected'])
        self.assertEqual(data[0]['configured'],{'google':True,'microsoft':True})
        for role in ('administrator','setter'):
            Membership.objects.filter(pk=self.grant.pk).update(role=role)
            self.assertEqual(self.client.get(self.base).data['connections'],[])
            self.assertEqual(self.client.post(self.start_url,{'provider':'google'},format='json').status_code,403)
        Membership.objects.create(user=self.user,workspace='isolation',role='client')
        self.assertEqual(self.client.post(self.base+'isolation/start/',{'provider':'microsoft'},format='json').status_code,200)
    def test_start_pkce_scopes_session_binding_and_sealed_verifier(self):
        state=self.start();attempt=CalendarAuthorization.objects.get();self.assertNotEqual(attempt.state_hash,state)
        self.assertEqual(len(unseal(attempt.verifier)),86)
        self.assertNotIn('private',str(self.client.get(self.base).data))
        other=APIClient();other.force_login(self.user)
        with patch('packages.calendar_connectors.providers.tokens') as exchange:
            self.assertEqual(other.post(self.callback_url,{'state':state,'code':'code'},format='json').status_code,400);exchange.assert_not_called()
        response=self.client.post(self.start_url,{'provider':'google','redirect_uri':'https://attacker.invalid'},format='json');self.assertEqual(response.status_code,400)
        self.assertEqual(self.client.post(self.start_url,{'provider':'calendly'},format='json').status_code,400)
    def test_connection_callback_is_single_use_tokens_encrypted_and_private(self):
        state=self.start()
        with patch('packages.calendar_connectors.providers.tokens',return_value=(TOKENS,3600)) as exchange:
            self.assertEqual(self.callback(state).status_code,200);self.assertEqual(self.callback(state).status_code,400);self.assertEqual(exchange.call_count,1)
        row=CalendarConnection.objects.get();self.assertTrue(row.connected);self.assertEqual(unseal(row.payload),TOKENS)
        self.assertNotIn(TOKENS['access'],row.payload);self.assertNotIn(TOKENS['refresh'],row.payload)
        self.assertEqual(CalendarAuthorization.objects.get().verifier,'')
        public=str(self.client.get(self.base).data)+str(list(AccessAudit.objects.values()))
        for secret in (*TOKENS.values(),'single-use-code',state):self.assertNotIn(secret,public)
    def test_expiry_refusal_and_revoked_role_stop_exchange(self):
        state=self.start();CalendarAuthorization.objects.update(expires_at=timezone.now()-timedelta(seconds=1))
        with patch('packages.calendar_connectors.providers.tokens') as exchange:
            self.assertEqual(self.callback(state).status_code,400)
            state=self.start();self.assertEqual(self.client.post(self.callback_url,{'state':state,'error':'access_denied'},format='json').status_code,400)
            self.assertEqual(self.callback(state).status_code,400)
            state=self.start();Membership.objects.filter(pk=self.grant.pk).update(active=False)
            self.assertEqual(self.callback(state).status_code,403);exchange.assert_not_called()
    def test_busy_refreshes_and_rotates_tokens_without_private_event_data(self):
        row=self.connected();CalendarConnection.objects.filter(pk=row.pk).update(expires_at=timezone.now())
        periods=[{'start':'2026-12-01T10:00:00+00:00','end':'2026-12-01T11:00:00+00:00'}]
        renewed={'access':'renewed-access','refresh':'rotated-refresh'}
        with patch('packages.calendar_connectors.providers.tokens',return_value=(renewed,3600)) as refresh,patch('packages.calendar_connectors.providers.busy',return_value=periods):
            first=self.client.post(self.base+'assurance/busy/',self.window,format='json');self.assertEqual(first.status_code,200)
            self.assertEqual(first.data['busy'],periods);self.assertEqual(first['Cache-Control'],'no-store')
            self.assertEqual(self.client.post(self.base+'assurance/busy/',self.window,format='json').status_code,200);self.assertEqual(refresh.call_count,1)
        row.refresh_from_db();self.assertEqual(unseal(row.payload),renewed)
    def test_provider_revocation_is_not_free_time_and_persists_reconnect_state(self):
        self.connected();CalendarConnection.objects.update(auto_sync=True)
        with patch('packages.calendar_connectors.providers.busy',side_effect=providers.ProviderError(True)):
            response=self.client.post(self.base+'assurance/busy/',self.window,format='json')
        self.assertEqual(response.status_code,503);self.assertNotIn('busy',response.data)
        row=CalendarConnection.objects.get();self.assertFalse(row.connected);self.assertFalse(row.auto_sync);self.assertEqual(row.payload,'')
    def test_disconnect_clears_tokens_pending_consent_and_is_owner_only(self):
        row=self.connected();state=self.start()
        self.assertEqual(self.client.post(self.base+'assurance/disconnect/',{'revision':row.revision},format='json').status_code,204)
        row.refresh_from_db();self.assertEqual(row.payload,'');self.assertFalse(row.connected)
        self.assertEqual(self.callback(state).status_code,400)
        self.assertEqual(self.client.post(self.base+'assurance/disconnect/',{'revision':1},format='json').status_code,400)
    def test_disconnect_during_exchange_prevents_old_consent_from_reconnecting(self):
        state=self.start()
        def exchange(*args,**kwargs):
            self.assertEqual(self.client.post(self.base+'assurance/disconnect/',{'revision':0},format='json').status_code,204)
            return TOKENS,3600
        with patch('packages.calendar_connectors.providers.tokens',side_effect=exchange):self.assertEqual(self.callback(state).status_code,400)
        self.assertFalse(CalendarConnection.objects.get().connected)
    def test_invalid_windows_missing_config_and_csrf_do_not_contact_provider(self):
        self.connected()
        with patch('packages.calendar_connectors.providers.busy') as busy:
            for changes in ({'starts_at':'2026-12-03T00:00:00Z'},{'ends_at':'2027-02-01T00:00:00Z'},{'starts_at':'2026-12-01T10:00:00'},{'user_id':99}):
                self.assertEqual(self.client.post(self.base+'assurance/busy/',{**self.window,**changes},format='json').status_code,400)
            busy.assert_not_called()
        csrf=APIClient(enforce_csrf_checks=True);csrf.force_login(self.user)
        self.assertEqual(csrf.post(self.start_url,{'provider':'google'},format='json').status_code,403)
        with override_settings(GOOGLE_CALENDAR_CLIENT_SECRET=''):
            self.assertFalse(self.client.get(self.base).data['connections'][0]['configured']['google'])
            self.assertEqual(self.client.post(self.start_url,{'provider':'google'},format='json').status_code,503)
    def test_audit_failure_rolls_back_connection_without_replaying_consent(self):
        state=self.start()
        with patch('packages.calendar_connectors.providers.tokens',return_value=(TOKENS,3600)),patch('portal.backend.identity.calendars.AccessAudit.objects.create',side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):self.callback(state)
        self.assertFalse(CalendarConnection.objects.get().connected);self.assertTrue(CalendarAuthorization.objects.get().used)

@override_settings(**OPTIONS)
class ProviderAdapterTests(TestCase):
    def response(self,data,status=200):return Mock(status_code=status,content=b'{}',json=Mock(return_value=data))
    def test_token_scopes_refresh_and_pkce_parameters(self):
        data={'access_token':'a','refresh_token':'r','expires_in':3600,'token_type':'Bearer','scope':' '.join(providers.GOOGLE_SCOPES)}
        with patch('packages.calendar_connectors.providers.requests.request',return_value=self.response(data)) as http:
            tokens,_=providers.tokens('google',{'client_id':'id','client_secret':'secret','tenant':'common'},code='code',redirect='https://local.invalid/crm/oauth/google',verifier='verifier')
            self.assertEqual(tokens,{'access':'a','refresh':'r'});self.assertEqual(http.call_args.kwargs['data']['code_verifier'],'verifier');self.assertFalse(http.call_args.kwargs['allow_redirects'])
        data['scope']='unrelated'
        with patch('packages.calendar_connectors.providers.requests.request',return_value=self.response(data)):
            with self.assertRaises(providers.ProviderError):providers.tokens('google',{'client_id':'id','client_secret':'secret','tenant':'common'},refresh='r')
    def test_google_partial_failure_does_not_return_empty_success(self):
        now=timezone.now()
        with patch('packages.calendar_connectors.providers.requests.request',return_value=self.response({'calendars':{'primary':{'errors':[{'reason':'notFound'}]}}})):
            with self.assertRaises(providers.ProviderError):providers.busy('google','token',now,now+timedelta(days=1))
    def test_microsoft_strips_details_expands_pages_and_refuses_foreign_next_link(self):
        start=timezone.now();end=start+timedelta(days=1)
        event={'start':{'dateTime':start.isoformat(),'timeZone':'UTC'},'end':{'dateTime':end.isoformat(),'timeZone':'UTC'},'showAs':'busy','subject':'private title','organizer':'private organizer'}
        with patch('packages.calendar_connectors.providers.requests.request',return_value=self.response({'value':[event]})):
            result=providers.busy('microsoft','token',start,end);self.assertEqual(len(result),1);self.assertNotIn('private',str(result))
        next_url='https://graph.microsoft.com/v1.0/me/calendar/calendarView?$skiptoken=opaque'
        with patch('packages.calendar_connectors.providers.requests.request',side_effect=[self.response({'value':[event],'@odata.nextLink':next_url}),self.response({'value':[{**event,'showAs':'free'}]})]) as http:
            self.assertEqual(len(providers.busy('microsoft','token',start,end)),1);self.assertEqual(http.call_count,2)
        with patch('packages.calendar_connectors.providers.requests.request',return_value=self.response({'value':[],'@odata.nextLink':'https://evil.invalid/steal'})) as http:
            with self.assertRaises(providers.ProviderError):providers.busy('microsoft','token',start,end)
            self.assertEqual(http.call_count,1)

@skipUnless(connection.vendor=='postgresql','Calendar concurrency requires PostgreSQL')
@override_settings(**OPTIONS)
class CalendarConcurrencyTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.user=get_user_model().objects.create_user('advisor',password='strong-password-test')
        Membership.objects.create(user=self.user,workspace='assurance',role='advisor')
        self.clients=[APIClient(),APIClient()]
        for client in self.clients:client.force_login(self.user)
    def race(self,path,body):
        def attempt(client):
            close_old_connections()
            try:return client.post(path,body,format='json').status_code
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:return sorted(pool.map(attempt,self.clients))
    def test_same_authorization_can_only_be_exchanged_once(self):
        result=self.clients[0].post('/api/portal/calendar/assurance/start/',{'provider':'google'},format='json')
        state=parse_qs(urlsplit(result.data['authorization_url']).query)['state'][0]
        self.clients[1].cookies=self.clients[0].cookies.copy()
        with patch('packages.calendar_connectors.providers.tokens',return_value=(TOKENS,3600)) as exchange:
            self.assertEqual(self.race('/api/portal/calendar/callback/google/',{'state':state,'code':'one-code'}),[200,400]);self.assertEqual(exchange.call_count,1)
    def test_concurrent_availability_rotates_refresh_token_once(self):
        CalendarConnection.objects.create(user=self.user,workspace='assurance',provider='google',connected=True,payload=seal(TOKENS),expires_at=timezone.now())
        with patch('packages.calendar_connectors.providers.tokens',return_value=({'access':'next','refresh':'rotated'},3600)) as refresh,patch('packages.calendar_connectors.providers.busy',return_value=[]):
            self.assertEqual(self.race('/api/portal/calendar/assurance/busy/',{'starts_at':'2026-12-01T00:00:00Z','ends_at':'2026-12-02T00:00:00Z'}),[200,200]);self.assertEqual(refresh.call_count,1)
