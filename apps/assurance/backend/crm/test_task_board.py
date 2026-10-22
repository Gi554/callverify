from copy import copy
from datetime import timedelta
from uuid import uuid4
from django.test import TestCase,override_settings
from django.utils import timezone
from packages.access.tickets import issue
from .models import FollowUpTask
from .test_task_assignment import task_fixture


@override_settings(DEBUG=True)
class TaskBoardTests(TestCase):
    def setUp(self):
        self.client,self.task,self.url=task_fixture()
        self.auth(21)
        self.task.due_at=timezone.now()+timedelta(days=1)
        self.task.save()
        self.late=self.clone(priority='urgent',due_at=timezone.now()-timedelta(hours=1),reason='Rappel important')
        self.closed=self.clone(closed_at=timezone.now(),resolution='Prospect recontacté')
        self.foreign=self.clone(setter_id=22,priority='urgent')

    def auth(self,pk,role='setter'):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+issue(pk,'assurance',role))

    def clone(self,**changes):
        appointment=copy(self.task.appointment)
        appointment.pk=None;appointment.request_id=uuid4();appointment.save()
        return FollowUpTask.objects.create(appointment=appointment,setter_id=changes.pop('setter_id',21),
            due_at=changes.pop('due_at',self.task.due_at),reason=changes.pop('reason','Suivi'),**changes)

    def summary(self,**query):
        return self.client.get('/api/assurance/follow-ups/summary/',{'state':'all',**query})

    def test_mutually_exclusive_columns_and_scoped_totals(self):
        for bucket,task in [('todo',self.task),('overdue',self.late),('closed',self.closed)]:
            data=self.client.get('/api/assurance/follow-ups/',{'state':'all','bucket':bucket}).data
            self.assertEqual(data['count'],1)
            self.assertEqual(data['results'][0]['id'],task.pk)
        data=self.summary().data
        self.assertEqual({key:data[key] for key in ('total','open','todo','overdue','closed')},
            {'total':3,'open':2,'todo':1,'overdue':1,'closed':1})
        self.assertEqual(data['open_priorities'],{'urgent':1,'high':0,'normal':1,'low':0})
        self.auth(22);self.assertEqual(self.summary().data['total'],1)
        self.auth(31,'advisor');self.assertEqual(self.summary().status_code,403)

    def test_search_and_priority_apply_to_summary_and_cards(self):
        query={'state':'all','priority':'urgent','search':'important'}
        data=self.client.get('/api/assurance/follow-ups/',query).data
        self.assertEqual(data['count'],1);self.assertEqual(data['results'][0]['id'],self.late.pk)
        self.assertEqual(self.summary(priority='urgent',search='important').data['total'],1)
        self.assertEqual(self.summary(search='not-present').data['total'],0)
        for query in ({'bucket':'invented'},{'priority':'invented'}):
            self.assertEqual(self.summary(**query).status_code,400)

    def test_closing_moves_task_without_changing_another_setters_task(self):
        self.assertEqual(self.client.post(self.url+'close/',{'revision':self.task.revision,'resolution':'Suivi terminé'},format='json').status_code,200)
        data=self.summary().data
        self.assertEqual((data['open'],data['closed'],data['total']),(1,2,3))
        self.assertEqual(self.client.post(f'/api/assurance/follow-ups/{self.foreign.pk}/close/',{'revision':0,'resolution':'Non autorisé'},format='json').status_code,404)
        self.foreign.refresh_from_db();self.assertIsNone(self.foreign.closed_at)

    def test_column_pagination_keeps_full_total(self):
        for _ in range(26):self.clone()
        first=self.client.get('/api/assurance/follow-ups/',{'state':'all','bucket':'todo'}).data
        second=self.client.get('/api/assurance/follow-ups/',{'state':'all','bucket':'todo','page':2}).data
        self.assertEqual(first['count'],27);self.assertEqual(len(first['results']),25)
        self.assertEqual(len(second['results']),2);self.assertIsNotNone(first['next'])
        self.assertEqual(self.summary().data['total'],29)
