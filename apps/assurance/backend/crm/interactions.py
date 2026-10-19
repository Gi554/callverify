"""Read-only contact chronology; visibility is applied before SQL union/pagination."""
from django.db.models import F,Value,CharField,TextField,Case,When,Q
from django.db.models.functions import Cast
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from .models import ContactNote,ContactDocument,Appointment,AppointmentReport,AppointmentIncident

KINDS=('note','document','appointment','report','incident')

def window(params):
    result={}
    for name in ('after','before'):
        raw=params.get(name,'')
        if not raw:continue
        try:value=parse_datetime(raw) if len(raw)<=100 else None
        except (ValueError,TypeError):value=None
        if value is None or timezone.is_naive(value):raise ValidationError('Dates ISO 8601 avec décalage explicite requises')
        result[name]=value
    if len(result)==2 and result['after']>result['before']:raise ValidationError('Intervalle inversé')
    return result


def entries(qs,kind,detail,state,reference,dates):
    if 'after' in dates:qs=qs.filter(created_at__gte=dates['after'])
    if 'before' in dates:qs=qs.filter(created_at__lte=dates['before'])
    return qs.order_by().annotate(event_type=Value(kind,output_field=CharField()),event_id=F('pk'),
        occurred_at=F('created_at'),detail=Cast(detail,TextField()),state=Cast(state,TextField()),reference_id=reference
    ).values('event_type','event_id','occurred_at','detail','state','reference_id')

class ContactInteractionMixin:
    @action(detail=True,methods=['get'])
    def interactions(self,request,pk=None):
        contact=self.get_object();user=request.user
        kind=request.query_params.get('type','')
        if kind and kind not in KINDS:raise ValidationError('Type d’interaction invalide')
        dates=window(request.query_params)
        notes=ContactNote.objects.filter(contact=contact)
        documents=ContactDocument.objects.filter(contact=contact)
        appointments=Appointment.objects.filter(contact=contact)
        if user.role=='advisor':
            notes=notes.filter(channel='advisor',author_id=user.pk)
            documents=documents.filter(Q(channel='advisor',author_id=user.pk)|Q(channel='internal',advisor_visible=True))
            appointments=appointments.filter(advisor_id=user.pk)
        elif user.role=='setter':
            notes=notes.filter(channel='internal');documents=documents.filter(channel='internal')
            appointments=appointments.filter(setter_id=user.pk)
        reports=AppointmentReport.objects.filter(appointment__in=appointments.values('pk'))
        incidents=AppointmentIncident.objects.filter(appointment__in=appointments.values('pk'))
        sources={
            'note':(notes,F('body'),F('channel'),F('pk')),
            'document':(documents,Case(When(channel='internal',then=F('advisor_filename')),default=F('filename'),output_field=CharField()) if user.role=='advisor' else F('filename'),Case(When(channel='internal',then=Value('shared')),default=F('channel'),output_field=CharField()) if user.role=='advisor' else F('channel'),F('pk')),
            'appointment':(appointments,Value(''),F('status'),F('pk')),
            'report':(reports,F('note'),Case(When(performed=True,then=Value('performed')),default=Value('not_performed'),output_field=CharField()),F('appointment_id')),
            'incident':(incidents,F('note'),Value('reported'),F('appointment_id')),
        }
        queries=[entries(qs,key,detail,state,reference,dates) for key,(qs,detail,state,reference) in sources.items() if not kind or key==kind]
        qs=queries[0].union(*queries[1:],all=True).order_by('-occurred_at','event_type','-event_id') if len(queries)>1 else queries[0].order_by('-occurred_at','event_type','-event_id')
        response=self.get_paginated_response(list(self.paginate_queryset(qs)))
        response['Cache-Control']='no-store';return response
