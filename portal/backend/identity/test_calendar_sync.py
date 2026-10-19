from datetime import timedelta
from uuid import uuid4
from unittest import skipUnless
from unittest.mock import patch,Mock
from concurrent.futures import ThreadPoolExecutor
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection,close_old_connections
from django.test import TestCase,TransactionTestCase,override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.calendar_connectors import events,providers
from . import calendar_sync as sync
from .models import CalendarConnection,CalendarSync,Membership,AccessAudit
from .calendars import seal,Unavailable
from .test_calendars import OPTIONS,TOKENS

@override_settings(**OPTIONS)
class SyncTests(TestCase):
    def setUp(self):
        cache.clear();self.user=get_user_model().objects.create_user('owner',password='strong-test-password')
        Membership.objects.create(user=self.user,workspace='assurance',role='advisor')
        self.row=CalendarConnection.objects.create(user=self.user,workspace='assurance',provider='google',payload=seal(TOKENS),connected=True,auto_sync=True,expires_at=timezone.now()+timedelta(hours=1))
        self.client=APIClient();self.client.force_login(self.user);self.base='/api/portal/calendar/assurance/'
        start=timezone.now()+timedelta(days=1)
        self.source={'id':41,'revision':0,'status':'scheduled','starts_at':start,'ends_at':start+timedelta(hours=1)}
    def remote(self):
        ledger=CalendarSync.objects.get()
        return {'id':'remote','etag':'v1','start':{'dateTime':ledger.expected_start.isoformat()},'end':{'dateTime':ledger.expected_end.isoformat()}}
    def run_sync(self,remote=None,error=None):
        with patch.object(sync,'source',return_value=self.source),patch.object(events,'find',return_value=remote),patch.object(events,'publish',return_value='remote',side_effect=error) as publish,patch.object(events,'remove') as remove:
            state=sync.sync_one(self.row,41)
        return state,publish,remove
    def test_create_idempotent_reschedule_and_cancel(self):
        self.assertEqual(self.run_sync()[0],'synced');ledger=CalendarSync.objects.get();key=ledger.key
        state,publish,_=self.run_sync(self.remote());self.assertEqual(state,'synced');publish.assert_not_called()
        remote=self.remote();self.source['starts_at']+=timedelta(hours=2);self.source['ends_at']+=timedelta(hours=2);self.source['revision']=1
        state,publish,_=self.run_sync(remote);self.assertEqual(state,'synced');publish.assert_called_once();self.assertEqual(CalendarSync.objects.get().key,key)
        self.source['status']='cancelled';state,publish,remove=self.run_sync(self.remote());self.assertEqual(state,'removed');remove.assert_called_once();publish.assert_not_called()
    def test_ambiguous_creation_is_not_reposted_and_recovery_uses_durable_key(self):
        self.assertEqual(self.run_sync(error=providers.ProviderError())[0],'error')
        ledger=CalendarSync.objects.get();self.assertTrue(ledger.create_attempted);key=ledger.key
        state,publish,_=self.run_sync();self.assertEqual(state,'error');publish.assert_not_called();self.assertEqual(CalendarSync.objects.get().error_code,'uncertain_create')
        state,publish,_=self.run_sync(self.remote());self.assertEqual(state,'synced');self.assertIsNotNone(publish.call_args.args[-1]);self.assertEqual(CalendarSync.objects.get().key,key)
    def test_known_slot_conflict_can_retry_but_external_edit_blocks_update(self):
        self.run_sync(error=providers.ProviderError(code='slot_busy'));self.assertFalse(CalendarSync.objects.get().create_attempted)
        self.assertEqual(self.run_sync()[0],'synced');remote=self.remote();remote['start']['dateTime']=(self.source['starts_at']+timedelta(minutes=1)).isoformat()
        state,publish,_=self.run_sync(remote);self.assertEqual(state,'error');publish.assert_not_called();self.assertEqual(CalendarSync.objects.get().error_code,'event_changed')
    def test_pause_role_revocation_and_refresh_revocation(self):
        self.row.auto_sync=False;self.row.save()
        with patch.object(sync,'source',return_value=self.source),patch.object(events,'find') as find:self.assertEqual(sync.sync_one(self.row,41),'paused');find.assert_not_called()
        self.row.auto_sync=True;self.row.save()
        with patch.object(sync,'source',return_value=self.source),patch.object(events,'find',side_effect=providers.ProviderError(True)):self.assertEqual(sync.sync_one(self.row,41),'error')
        self.row.refresh_from_db();self.assertFalse(self.row.connected);self.assertFalse(self.row.auto_sync);self.assertEqual(self.row.payload,'')
        Membership.objects.update(active=False)
        self.assertEqual(self.client.get(self.base+'sync/').status_code,403)
    def test_internal_change_during_external_write_stays_pending(self):
        modified={**self.source,'ends_at':self.source['ends_at']+timedelta(minutes=5),'revision':1}
        with patch.object(sync,'source',side_effect=[self.source,self.source,modified]),patch.object(events,'find',return_value=None),patch.object(events,'publish',return_value='remote'):
            self.assertEqual(sync.sync_one(self.row,41),'pending')
        self.assertEqual(CalendarSync.objects.get().error_code,'source_changed')
    def test_cancel_missing_unknown_and_future_source_only(self):
        self.source['status']='cancelled';self.assertEqual(self.run_sync()[0],'skipped');self.assertFalse(CalendarSync.objects.exists())
        self.source['status']='scheduled';self.source['ends_at']=timezone.now()-timedelta(hours=1);self.assertEqual(self.run_sync()[0],'skipped')
    def test_configuration_revision_list_privacy_and_cleanup_guard(self):
        self.run_sync();self.row.refresh_from_db()
        self.assertEqual(self.client.post(self.base+'start/',{'provider':'google'},format='json').status_code,400)
        self.assertEqual(self.client.post(self.base+'disconnect/',{'revision':self.row.revision},format='json').status_code,400)
        self.assertEqual(self.client.post(self.base+'sync-config/',{'revision':999,'enabled':False},format='json').status_code,400)
        self.assertEqual(self.client.post(self.base+'sync-config/',{'revision':self.row.revision,'enabled':False},format='json').status_code,204)
        self.assertEqual(self.client.post(self.base+'sync/',{},format='json').status_code,400)
        result=self.client.get(self.base+'sync/');self.assertEqual(result.status_code,200);self.assertEqual(result['Cache-Control'],'no-store')
        self.assertNotIn('remote_id',str(result.data));self.assertNotIn(str(CalendarSync.objects.get().key),str(result.data))
    def test_withdraw_stops_sync_and_deletes_only_recorded_event(self):
        self.run_sync()
        with patch.object(events,'find',return_value=self.remote()),patch.object(events,'remove') as remove:
            response=self.client.post(self.base+'withdraw/',{'confirm':True},format='json')
        self.assertEqual(response.status_code,200);remove.assert_called_once();self.assertEqual(response.data['counts'],{'removed':1})
        self.row.refresh_from_db();self.assertFalse(self.row.auto_sync)
        self.assertEqual(self.client.post(self.base+'disconnect/',{'revision':self.row.revision},format='json').status_code,204)
    def test_detach_requires_password_revision_ack_and_never_calls_provider(self):
        self.run_sync();self.row.refresh_from_db()
        body={'revision':self.row.revision,'current_password':'bad','confirm_external_cleanup':True}
        self.assertEqual(self.client.post(self.base+'detach/',body,format='json').status_code,400)
        body['current_password']='strong-test-password';body['confirm_external_cleanup']=False
        self.assertEqual(self.client.post(self.base+'detach/',body,format='json').status_code,400)
        body['confirm_external_cleanup']=True
        with patch.object(events,'remove') as remove,patch.object(events,'find') as find:
            self.assertEqual(self.client.post(self.base+'detach/',body,format='json').status_code,204);remove.assert_not_called();find.assert_not_called()
        self.row.refresh_from_db();self.assertFalse(self.row.connected);self.assertEqual(self.row.payload,'');self.assertEqual(CalendarSync.objects.get().status,'abandoned')
        self.assertTrue(AccessAudit.objects.filter(action='calendar.manual_cleanup_acknowledged').exists())
        self.assertEqual(self.client.post(self.base+'start/',{'provider':'microsoft'},format='json').status_code,200)
    def test_csrf_and_audit_rollback_for_detach(self):
        self.run_sync();self.row.refresh_from_db();body={'revision':self.row.revision,'current_password':'strong-test-password','confirm_external_cleanup':True}
        csrf=APIClient(enforce_csrf_checks=True);csrf.force_login(self.user)
        self.assertEqual(csrf.post(self.base+'detach/',body,format='json').status_code,403)
        with patch.object(AccessAudit.objects,'create',side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):self.client.post(self.base+'detach/',body,format='json')
        self.row.refresh_from_db();self.assertTrue(self.row.connected);self.assertEqual(CalendarSync.objects.get().status,'synced')
    def test_audit_failure_keeps_creation_intent_to_recover_without_duplicate(self):
        with patch.object(sync,'source',return_value=self.source),patch.object(events,'find',return_value=None),patch.object(events,'publish',return_value='remote') as send,patch.object(AccessAudit.objects,'create',side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):sync.sync_one(self.row,41)
            send.assert_called_once()
        ledger=CalendarSync.objects.get();self.assertTrue(ledger.create_attempted);self.assertEqual(ledger.remote_id,'')
        state,publish,_=self.run_sync();self.assertEqual(state,'error');publish.assert_not_called()

    def test_source_api_owner_validation_and_discovery(self):
        raw={**self.source,'starts_at':self.source['starts_at'].isoformat(),'ends_at':self.source['ends_at'].isoformat(),'advisor':{'id':self.user.pk}}
        response=Mock(status_code=200,content=b'{}',json=Mock(return_value=raw))
        with patch.object(sync.requests,'get',return_value=response) as http:
            self.assertEqual(sync.source(self.user,'assurance',41)['id'],41);self.assertIn('/api/assurance/appointments/41/',http.call_args.args[0]);self.assertFalse(http.call_args.kwargs['allow_redirects'])
            self.assertEqual(http.call_args.kwargs['headers']['X-Forwarded-Proto'],'https')
            raw['advisor']['id']=999
            with self.assertRaises(Unavailable):sync.source(self.user,'assurance',41)
        Membership.objects.create(user=self.user,workspace='isolation',role='client')
        raw.pop('advisor');raw['client']={'id':self.user.pk}
        with patch.object(sync.requests,'get',return_value=response) as http:
            self.assertEqual(sync.source(self.user,'isolation',41)['id'],41);self.assertIn('/api/visits/41/',http.call_args.args[0])
        with patch.object(sync,'fetch_source',side_effect=[{'results':[{'id':41}],'next':'page2'},{'results':[{'id':42}],'next':None}]),patch.object(sync,'sync_one',return_value='synced') as one:
            self.assertEqual(sync.sync_connection(self.row),{'synced':2});self.assertEqual(one.call_count,2)

class EventAdapterTests(TestCase):
    def setUp(self):
        self.key=uuid4();self.start=timezone.now();self.source={'id':7,'starts_at':self.start,'ends_at':self.start+timedelta(hours=1)}
    def test_create_private_no_attendees_stable_keys_and_preflight(self):
        for provider in ('google','microsoft'):
            with patch.object(events,'busy',return_value=[]),patch.object(events,'http',return_value={'id':'remote'}) as http:
                events.publish(provider,'secret',self.key,'isolation',self.source,None)
                payload=http.call_args.kwargs['json'];self.assertNotIn('attendees',payload);self.assertNotIn('Setter',str(payload))
                if provider=='google':self.assertEqual(payload['id'],'a'+self.key.hex);self.assertEqual(http.call_args.kwargs['params'],{'sendUpdates':'none'})
                else:self.assertEqual(payload['transactionId'],str(self.key));self.assertEqual(payload['singleValueExtendedProperties'][0]['value'],str(self.key))
            with patch.object(events,'busy',return_value=[{'start':'busy'}]),patch.object(events,'http') as http:
                with self.assertRaises(providers.ProviderError):events.publish(provider,'secret',self.key,'isolation',self.source,None)
                http.assert_not_called()
    def test_find_requires_marker_unique_result_and_no_attendees(self):
        with patch.object(events,'http',return_value={'id':'foreign','extendedProperties':{'private':{'amxSync':'wrong'}}}):
            with self.assertRaises(providers.ProviderError):events.find('google','secret',self.key)
        for rows in ([{'id':'x','attendees':[{'emailAddress':'private'}]}],[{'id':'x'},{'id':'y'}]):
            with patch.object(events,'http',return_value={'value':rows}):
                with self.assertRaises(providers.ProviderError):events.find('microsoft','secret',self.key)
        with patch.object(events,'http',return_value={'_status':404}):self.assertIsNone(events.find('google','secret',self.key))
    def test_reschedule_excludes_own_event_and_preserves_etag(self):
        with patch.object(events,'busy',return_value=[]) as busy,patch.object(events,'http',return_value={'id':'remote'}) as http:
            events.publish('google','secret',self.key,'assurance',self.source,{'id':'remote','etag':'v1'})
            self.assertEqual(busy.call_args.kwargs['exclude_id'],'remote');self.assertEqual(http.call_args.args[0],'PATCH');self.assertEqual(http.call_args.kwargs['headers']['If-Match'],'v1')
        with patch.object(events,'http') as http:
            with self.assertRaises(providers.ProviderError):events.remove('microsoft','secret',{'id':'remote'})
            http.assert_not_called()
        with patch.object(events,'http',return_value={'items':[]}):self.assertEqual(events.google_busy_except('secret',self.start,self.source['ends_at'],'remote'),[])
        with patch.object(events,'http',return_value={'timeZone':'UTC','items':[{'id':'other','start':{'date':self.start.date().isoformat()},'end':{'date':(self.start+timedelta(days=1)).date().isoformat()}}]}):
            self.assertEqual(len(events.google_busy_except('secret',self.start,self.source['ends_at'],'remote')),1)

@skipUnless(connection.vendor=='postgresql','Calendar synchronization concurrency requires PostgreSQL')
@override_settings(**OPTIONS)
class SyncConcurrencyTests(TransactionTestCase):
    def test_two_workers_never_create_twice(self):
        user=get_user_model().objects.create_user('owner');Membership.objects.create(user=user,workspace='assurance',role='advisor')
        row=CalendarConnection.objects.create(user=user,workspace='assurance',provider='google',payload=seal(TOKENS),connected=True,auto_sync=True,expires_at=timezone.now()+timedelta(hours=1))
        start=timezone.now()+timedelta(days=1);source={'id':41,'revision':0,'status':'scheduled','starts_at':start,'ends_at':start+timedelta(hours=1)}
        remote={}
        def publish(*args):
            remote.update(id='remote',start={'dateTime':start.isoformat()},end={'dateTime':source['ends_at'].isoformat()});return 'remote'
        def worker(_):
            close_old_connections()
            try:return sync.sync_one(CalendarConnection.objects.select_related('user').get(pk=row.pk),41)
            finally:close_old_connections()
        with patch.object(sync,'source',return_value=source),patch.object(events,'find',side_effect=lambda *args:dict(remote) if remote else None),patch.object(events,'publish',side_effect=publish) as send:
            with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(worker,range(2)))
        self.assertEqual(send.call_count,1);self.assertEqual(CalendarSync.objects.count(),1)
