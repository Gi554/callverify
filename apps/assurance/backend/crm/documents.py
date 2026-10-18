"""Private, append-only attachments. Bytes and audit commit in the same transaction."""
import hashlib
from datetime import timedelta
from pathlib import PurePosixPath
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django.utils.http import content_disposition_header
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import ContactDocument,BusinessAudit
from .leases import held,Conflict,LEASE_SECONDS

MAX_SIZE=5*1024*1024

class DocumentInput(serializers.Serializer):
    request_id=serializers.UUIDField()
    token=serializers.UUIDField(required=False,write_only=True)
    file=serializers.FileField(max_length=180)
    def validate(self,data):
        if set(self.initial_data)-set(self.fields):raise serializers.ValidationError('Champs non autorisés')
        upload=data['file']
        if upload.size>MAX_SIZE:raise serializers.ValidationError('Fichier limité à 5 Mo')
        content=upload.read(MAX_SIZE+1)
        if not content or len(content)>MAX_SIZE:raise serializers.ValidationError('Fichier vide ou trop volumineux')
        name=PurePosixPath(upload.name.replace('\\','/')).name
        if any(ord(c)<32 or ord(c)==127 for c in name):raise serializers.ValidationError('Nom de fichier invalide')
        extension=PurePosixPath(name).suffix.lower()
        signatures={'.pdf':(b'%PDF-','application/pdf'),'.png':(b'\x89PNG\r\n\x1a\n','image/png'),
            '.jpg':(b'\xff\xd8\xff','image/jpeg'),'.jpeg':(b'\xff\xd8\xff','image/jpeg')}
        signature,mime=signatures.get(extension,(None,None))
        if not signature or not content.startswith(signature):raise serializers.ValidationError('PDF, PNG ou JPEG avec signature correspondante requis')
        data.update(content=content,filename=name,content_type=mime,sha256=hashlib.sha256(content).hexdigest())
        return data

def output(row,user):
    result={key:getattr(row,key) for key in ('id','filename','content_type','size','channel','created_at')}
    if user.role=='administrator':result['author_id']=row.author_id
    return result

class ContactDocumentMixin:
    def document_queryset(self,contact):
        user=self.request.user
        qs=ContactDocument.objects.filter(contact=contact)
        if user.role=='advisor':qs=qs.filter(channel='advisor',author_id=user.pk)
        elif user.role=='setter':qs=qs.filter(channel='internal')
        return qs

    @action(detail=True,methods=['get','post'])
    def documents(self,request,pk=None):
        contact=self.get_object();user=request.user
        if request.method=='GET':
            qs=self.document_queryset(contact).defer('content').order_by('-pk')
            response=self.get_paginated_response([output(row,user) for row in self.paginate_queryset(qs)])
            response['Cache-Control']='no-store'
            return response
        serializer=DocumentInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
        channel='advisor' if user.role=='advisor' else 'internal'
        def replay(row):
            if (row.contact_id,row.author_id,row.channel,row.filename,row.sha256)!=(contact.pk,user.pk,channel,data['filename'],data['sha256']):
                raise Conflict('Identifiant de document déjà utilisé')
            return Response(output(row,user))
        existing=ContactDocument.objects.defer('content').filter(request_id=data['request_id']).first()
        if existing:return replay(existing)
        with transaction.atomic():
            if channel=='internal':
                now=timezone.now()
                if not held(contact.pk,user,data.get('token'),now).update(lease_expires_at=now+timedelta(seconds=LEASE_SECONDS)):
                    raise Conflict('Prenez en charge la fiche avant d’ajouter un document interne')
            row,created=ContactDocument.objects.get_or_create(request_id=data['request_id'],defaults={
                'contact':contact,'author_id':user.pk,'channel':channel,'filename':data['filename'],
                'content_type':data['content_type'],'size':len(data['content']),'sha256':data['sha256'],'content':data['content']})
            if not created:return replay(row)
            BusinessAudit.objects.create(actor_id=user.pk,object_id=contact.pk,action='contact.document_added',
                metadata={'document_id':row.pk,'channel':channel,'size':row.size,'sha256':row.sha256})
        return Response(output(row,user),status=201)

    @action(detail=True,methods=['get'],url_path=r'documents/(?P<document_id>[0-9]+)/download')
    def download_document(self,request,pk=None,document_id=None):
        from django.shortcuts import get_object_or_404
        row=get_object_or_404(self.document_queryset(self.get_object()),pk=document_id)
        BusinessAudit.objects.create(actor_id=request.user.pk,object_id=row.contact_id,action='contact.document_downloaded',metadata={'document_id':row.pk})
        response=HttpResponse(bytes(row.content),content_type=row.content_type)
        response['Content-Disposition']=content_disposition_header(True,row.filename)
        response['Cache-Control']='no-store'
        response['X-Content-Type-Options']='nosniff'
        return response
