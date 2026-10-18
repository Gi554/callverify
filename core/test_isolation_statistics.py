from datetime import timedelta
from uuid import uuid4
from django.test import TestCase,override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from packages.access.tickets import issue
from .models import IsolationVisit,IsolationVisitResult,Prospect
from .test_isolation_activity import assigned_fixture

@override_settings(DEBUG=True,SECURE_SSL_REDIRECT=False)
class IsolationStatisticsTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear();self.prospect=assigned_fixture();self.client=APIClient();self.auth(91,'administrator')
        self.day=timezone.now().replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(days=2)
        self.url='/api/workspace-statistics/'
    def auth(self,pk,role,space='isolation'):self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(pk,space,role))
    def visit(self,setter=21,client=72,performed=None,outcome=None,**changes):
        row=IsolationVisit.objects.create(prospect=self.prospect,request_id=uuid4(),fingerprint='x',client_id=client,client_name='Client',
            setter_id=setter,setter_name=f'Setter {setter}',booked_by_id=91,starts_at=self.day,ends_at=self.day+timedelta(hours=1),timezone='UTC',**changes)
        if performed is not None:IsolationVisitResult.objects.create(visit=row,author_client_id=client,performed=performed,outcome=outcome or ('completed' if performed else 'not_performed'),note='Confidentiel')
        return row
    def test_counts_denominators_distinct_prospects_and_missing_results(self):
        self.visit(performed=True,outcome='interested');self.visit(performed=False);self.visit();self.visit(status='cancelled')
        data=self.client.get(self.url).data;values=data['totals']
        self.assertEqual(values['visits'],4);self.assertEqual(values['prospects'],1)
        self.assertEqual(values['reported'],2);self.assertEqual(values['performed'],1)
        self.assertEqual(values['not_performed'],1);self.assertEqual(values['results_due'],1)
        self.assertEqual(values['cancelled'],1);self.assertEqual(values['performed_rate'],50)
        self.assertEqual(values['interest_rate'],100)
        self.assertNotIn('Confidentiel',str(data));self.assertNotIn('raw_phone',str(data))
    def test_empty_rates_are_not_false_zero(self):
        self.visit();data=self.client.get(self.url).data['totals']
        self.assertIsNone(data['performed_rate']);self.assertIsNone(data['interest_rate'])
    def test_client_scope_applies_to_totals_groups_and_names(self):
        self.visit(performed=True);foreign=self.visit(setter=22,client=73,performed=False)
        foreign.setter_name='SECRET';foreign.save()
        self.auth(72,'client');result=self.client.get(self.url)
        self.assertEqual(result.data['totals']['visits'],1)
        self.assertEqual(result.data['setters']['count'],1);self.assertNotIn('SECRET',str(result.data))
        self.assertEqual(result['Cache-Control'],'no-store')
    def test_setter_scope_excludes_other_origins_and_transferred_prospects(self):
        self.visit();self.visit(setter=22)
        self.auth(21,'setter');data=self.client.get(self.url).data
        self.assertEqual(data['totals']['visits'],1);self.assertNotIn('setters',data)
        Prospect.objects.filter(pk=self.prospect.pk).update(assigned_setter_id=22)
        self.assertEqual(self.client.get(self.url).data['totals']['visits'],0)
        self.auth(91,'administrator');self.assertEqual(self.client.get(self.url).data['totals']['visits'],2)
    def test_period_boundaries_and_invalid_input(self):
        self.visit();day=self.day.date().isoformat()
        self.assertEqual(self.client.get(self.url,{'from':day,'to':day}).data['totals']['visits'],1)
        tomorrow=(self.day.date()+timedelta(days=1)).isoformat()
        self.assertEqual(self.client.get(self.url,{'from':tomorrow,'to':tomorrow}).data['totals']['visits'],0)
        for args in ({'from':'bad'},{'from':'2026-02-30'},{'from':'2026-01-02','to':'2026-01-01'},
            {'from':'2020-01-01','to':'2026-01-01'},{'from':'9999-12-31','to':'9999-12-31'},{'export':'pdf'}):
            self.assertEqual(self.client.get(self.url,args).status_code,400,args)
    def test_group_pagination_keeps_complete_totals(self):
        for index in range(27):self.visit(setter=100+index)
        first=self.client.get(self.url).data
        self.assertEqual(first['totals']['visits'],27);self.assertEqual(first['setters']['count'],27)
        self.assertEqual(len(first['setters']['results']),25)
        self.assertEqual(len(self.client.get(self.url,{'page':2}).data['setters']['results']),2)
    def test_future_and_pending_are_separate_and_auth_is_required(self):
        row=self.visit();row.starts_at=timezone.now()+timedelta(days=1);row.ends_at=row.starts_at+timedelta(hours=1);row.save()
        end=(timezone.now()+timedelta(days=2)).date().isoformat()
        values=self.client.get(self.url,{'to':end}).data['totals']
        self.assertEqual(values['upcoming'],1);self.assertEqual(values['results_due'],0)
        self.auth(21,'setter','assurance');self.assertEqual(self.client.get(self.url).status_code,401)
        self.client.credentials();self.assertEqual(self.client.get(self.url).status_code,401)
