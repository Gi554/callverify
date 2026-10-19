"""Internal notification inbox. Reading never mutates or closes a follow-up task."""
from django.db import transaction
from django.db.models import F,OuterRef,Subquery
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied,ValidationError,NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from .models import TaskNotification,TaskNotificationRead,FollowUpTask,BusinessAudit

LABELS={'report':'Compte rendu nécessitant un suivi','incident':'Nouveau signalement','existing':'Suivi déjà ouvert'}

def notify(task,kind,key):
    return TaskNotification.objects.get_or_create(event_key=key,defaults={'task':task,'kind':kind})[0]

def scoped(user):
    if user.role not in ('administrator','setter'):raise PermissionDenied('Notifications de suivi internes uniquement')
    qs=TaskNotification.objects.select_related('task')
    if user.role=='setter':qs=qs.filter(task__setter_id=user.pk)
    read=TaskNotificationRead.objects.filter(notification_id=OuterRef('pk'),user_id=user.pk)
    return qs.annotate(read_at=Subquery(read.values('read_at')[:1]))

def output(row):
    return {'id':row.pk,'task_id':row.task_id,'kind':row.kind,'label':LABELS[row.kind],
        'created_at':row.created_at,'read_at':row.read_at,'resolved':row.task.closed_at is not None,
        'priority':row.task.priority,'due_at':row.task.due_at}

class Pager(PageNumberPagination):page_size=25

class TaskNotificationViewSet(viewsets.GenericViewSet):
    pagination_class=Pager
    http_method_names=['get','post','head','options']
    def get_queryset(self):
        qs=scoped(self.request.user).order_by('-created_at','-pk')
        state=self.request.query_params.get('state','open')
        if state not in ('open','resolved','all'):raise ValidationError('Filtre de notifications invalide')
        if state!='all':qs=qs.filter(task__closed_at__isnull=state=='open')
        unread=self.request.query_params.get('unread','false')
        if unread not in ('true','false'):raise ValidationError('Filtre non lues invalide')
        if unread=='true':qs=qs.filter(read_at__isnull=True)
        return qs
    def list(self,request):
        response=self.get_paginated_response([output(row) for row in self.paginate_queryset(self.get_queryset())])
        response['Cache-Control']='no-store';return response
    @action(detail=False,methods=['get'])
    def summary(self,request):
        qs=scoped(request.user).filter(task__closed_at__isnull=True)
        response=Response({'open':qs.count(),'unread_open':qs.filter(read_at__isnull=True).count()})
        response['Cache-Control']='no-store';return response
    @action(detail=True,methods=['post'])
    def read(self,request,pk=None):
        if request.data:raise ValidationError('Aucun champ attendu')
        original=self.get_object()
        with transaction.atomic():
            # Same task lock as reassignment: a former owner cannot acknowledge after transfer.
            FollowUpTask.objects.filter(pk=original.task_id).update(revision=F('revision'))
            row=self.get_queryset().filter(pk=original.pk).first()
            if row is None:raise NotFound()
            receipt,created=TaskNotificationRead.objects.get_or_create(notification=row,user_id=request.user.pk)
            if created:BusinessAudit.objects.create(actor_id=request.user.pk,object_id=row.task.appointment_id,
                action='appointment.notification_read',metadata={'task_id':row.task_id,'notification_id':row.pk})
            row.read_at=receipt.read_at
        response=Response(output(row));response['Cache-Control']='no-store';return response
