"""Append-only notes with server-derived visibility; never forward internal notes to advisors."""
from datetime import timedelta
from django.db import transaction
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import ContactNote,BusinessAudit
from .leases import held,Conflict,LEASE_SECONDS
from django.utils import timezone

class NoteInput(serializers.Serializer):
    request_id=serializers.UUIDField()
    body=serializers.CharField(max_length=5000)
    token=serializers.UUIDField(required=False,write_only=True)
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise serializers.ValidationError('Champs non autorisés')
        return data

def output(row,user):
    result={'id':row.pk,'body':row.body,'created_at':row.created_at,'channel':row.channel}
    if user.role=='administrator':result['author_id']=row.author_id
    return result

class ContactNoteMixin:
    @action(detail=True,methods=['get','post'])
    def notes(self,request,pk=None):
        contact=self.get_object();user=request.user
        qs=ContactNote.objects.filter(contact=contact).order_by('-pk')
        if user.role=='advisor':qs=qs.filter(channel='advisor',author_id=user.pk)
        elif user.role=='setter':qs=qs.filter(channel='internal')
        if request.method=='GET':
            return self.get_paginated_response([output(row,user) for row in self.paginate_queryset(qs)])
        serializer=NoteInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
        channel='advisor' if user.role=='advisor' else 'internal'
        def replay(row):
            if row.contact_id!=contact.pk or row.author_id!=user.pk or row.channel!=channel or row.body!=data['body']:
                raise Conflict('Identifiant de note déjà utilisé')
            return Response(output(row,user))
        existing=ContactNote.objects.filter(request_id=data['request_id']).first()
        if existing:return replay(existing)
        with transaction.atomic():
            if channel=='internal':
                now=timezone.now()
                if not held(contact.pk,user,data.get('token'),now).update(lease_expires_at=now+timedelta(seconds=LEASE_SECONDS)):
                    raise Conflict('Prenez en charge la fiche avant d’ajouter une note interne')
            row,created=ContactNote.objects.get_or_create(request_id=data['request_id'],defaults={
                'contact':contact,'author_id':user.pk,'channel':channel,'body':data['body']})
            if not created:return replay(row)
            BusinessAudit.objects.create(actor_id=user.pk,object_id=contact.pk,action='contact.note_added',
                metadata={'note_id':row.pk,'channel':channel})
        return Response(output(row,user),status=201)
