"""Shared read-only resource checks; viewset get_object supplies the role scope."""
from django.core import signing
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied,ValidationError
from rest_framework.response import Response
from .phone_history import number,issue,verify

class HistoryMixin:
    history_workspace=''
    def history_source(self,row):
        return (row.phone,row.revision) if self.history_workspace=='assurance' else (row.phone.e164 if row.phone_id else row.raw_phone,row.assignment_revision)

    @action(detail=True,methods=['post'],url_path='phone-history-proof')
    def phone_history_proof(self,request,pk=None):
        if request.user.role!='setter':raise PermissionDenied('Historique de votre poste réservé au setter connecté.')
        if request.data or request.query_params:raise ValidationError('Aucun paramètre attendu.')
        row=self.get_object();raw,revision=self.history_source(row)
        try:destination=number(raw)
        except ValueError:raise ValidationError('Numéro nord-américain normalisé requis pour rapprocher le journal.') from None
        response=Response({'proof':issue(request.user.pk,row.pk,revision,destination,self.history_workspace),'expires_in':60})
        response['Cache-Control']='no-store';return response

    @action(detail=True,methods=['post'],url_path='phone-history-check')
    def phone_history_check(self,request,pk=None):
        if request.user.role!='setter':raise PermissionDenied('Setter requis.')
        if request.query_params or set(request.data)!={'proof'}:raise ValidationError('Preuve seule attendue.')
        try:data=verify(request.data['proof'],request.user.pk,self.history_workspace)
        except (signing.BadSignature,ValueError,TypeError,AttributeError):raise ValidationError('Preuve historique invalide ou expirée.') from None
        row=self.get_object();raw,revision=self.history_source(row)
        try:eligible=data['resource']==row.pk and data['revision']==revision and data['destination']==number(raw)
        except ValueError:eligible=False
        response=Response({'eligible':eligible});response['Cache-Control']='no-store';return response
