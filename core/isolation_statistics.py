"""Visit-start cohorts, attributed to the original setter, scoped before aggregation."""
from datetime import datetime,time,timedelta,timezone as utc
from django.db.models import Count,Q,Subquery,OuterRef
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.decorators import api_view,authentication_classes,permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from .isolation_work import VisitAuthentication
from .models import IsolationVisit,AuditEvent
from .isolation_statistics_export import response as export_response

def metrics(now):
    return {'visits':Count('pk',distinct=True),'prospects':Count('prospect_id',distinct=True),
        'cancelled':Count('pk',filter=Q(status='cancelled'),distinct=True),
        'upcoming':Count('pk',filter=Q(status='scheduled',starts_at__gt=now),distinct=True),
        'reported':Count('pk',filter=Q(result__isnull=False),distinct=True),
        'performed':Count('pk',filter=Q(result__performed=True),distinct=True),
        'not_performed':Count('pk',filter=Q(result__performed=False),distinct=True),
        'results_due':Count('pk',filter=Q(status='scheduled',ends_at__lte=now,result__isnull=True),distinct=True),
        'interested':Count('pk',filter=Q(result__outcome='interested'),distinct=True),
        'not_interested':Count('pk',filter=Q(result__outcome='not_interested'),distinct=True),
        'follow_up':Count('pk',filter=Q(result__outcome='follow_up'),distinct=True)}

def finish(row):
    row['performed_rate']=round(100*row['performed']/row['reported'],2) if row['reported'] else None
    row['interest_rate']=round(100*row['interested']/row['performed'],2) if row['performed'] else None
    return row

@api_view(['GET'])
@authentication_classes([VisitAuthentication])
@permission_classes([IsAuthenticated])
def statistics(request):
    now=timezone.now();today=now.date()
    kind=request.query_params.get('export','')
    if kind not in ('','csv','xlsx'):raise ValidationError('Export CSV ou XLSX uniquement')
    try:
        start=parse_date(request.query_params.get('from',(today-timedelta(days=29)).isoformat()))
        end=parse_date(request.query_params.get('to',today.isoformat()))
        if start is None or end is None or end<start or (end-start).days>365:raise ValueError()
        exclusive=end+timedelta(days=1)
    except (ValueError,OverflowError):raise ValidationError('Période AAAA-MM-JJ valide de 366 jours maximum requise')
    qs=IsolationVisit.objects.filter(starts_at__gte=datetime.combine(start,time.min,utc.utc),starts_at__lt=datetime.combine(exclusive,time.min,utc.utc))
    if request.user.role=='client':qs=qs.filter(client_id=request.user.pk)
    if request.user.role=='setter':qs=qs.filter(setter_id=request.user.pk,prospect__assigned_setter_id=request.user.pk)
    result={'from':start,'to':end,'timezone':'UTC','as_of':now,'totals':finish(qs.aggregate(**metrics(now))),
        'definition':'Période selon le début actuel de la visite en UTC. Attribution au setter d’origine. Client : ses visites uniquement. Setter : ses réservations dont il conserve le prospect. Un transfert retire donc les visites du périmètre de l’ancien setter. Taux effectué = Oui / résultats renseignés ; taux d’intérêt = intéressés / visites effectuées. Un résultat absent n’est pas Non. Les prospects sont distincts dans chaque groupe et ne sont pas additionnables entre setters.'}
    exported_groups=[]
    if request.user.role in ('administrator','client'):
        names=qs.filter(setter_id=OuterRef('setter_id')).order_by('-created_at','-pk').values('setter_name')[:1]
        groups=qs.order_by().values('setter_id').annotate(**metrics(now),setter_name=Subquery(names)).order_by('setter_id')
        if kind:
            if groups.count()>5000:raise ValidationError('Export limité à 5 000 setters ; réduisez la période')
            exported_groups=[finish(row) for row in groups]
        else:
            pager=PageNumberPagination();pager.page_size=25
            rows=pager.paginate_queryset(groups,request)
            result['setters']={'count':pager.page.paginator.count,'next':pager.get_next_link(),'previous':pager.get_previous_link(),
                'results':[finish(row) for row in rows]}
    if kind:
        response=export_response(result,exported_groups,kind)
        AuditEvent.objects.create(action='isolation.statistics.exported',metadata={'actor_portal_id':request.user.pk,
            'scope':request.user.role,'from':str(start),'to':str(end),'format':kind})
        return response
    response=Response(result);response['Cache-Control']='no-store'
    return response
