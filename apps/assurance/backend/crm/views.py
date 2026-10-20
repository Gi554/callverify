from rest_framework import serializers,viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .visibility import visible_contacts
from .agreements import AgreementMixin
from .models import Contact,Appointment,FollowUpTask
from django.utils import timezone
from .leases import ContactLeaseMixin
from .notes import ContactNoteMixin,NoteSharingMixin
from .interactions import ContactInteractionMixin
from .custom_fields import CustomValuesMixin
from .documents import ContactDocumentMixin,DocumentSharingMixin
from .pipeline import ContactPipelineMixin,pipeline
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination

class ContactPagination(PageNumberPagination):
    page_size=25

class PublicContactSerializer(serializers.ModelSerializer):
    status_label=serializers.SerializerMethodField()
    def get_status_label(self,obj):
        if 'stage_labels' not in self.context:self.context['stage_labels']={s['key']:s['label'] for s in pipeline().stages}
        return self.context['stage_labels'].get(obj.status,obj.status)
    # Deliberate allowlist: no setter identity, creator or actor metadata.
    class Meta:
        model=Contact
        fields=['id','name','phone','email','status','status_label','updated_at','revision']
        read_only_fields=['status','updated_at','revision']

class ContactViewSet(AgreementMixin,NoteSharingMixin,DocumentSharingMixin,ContactInteractionMixin,ContactPipelineMixin,ContactDocumentMixin,CustomValuesMixin,ContactNoteMixin,ContactLeaseMixin,viewsets.ReadOnlyModelViewSet):
    pagination_class=ContactPagination
    serializer_class=PublicContactSerializer
    http_method_names=['get','head','options','post','patch','delete']
    def get_queryset(self):
        qs=visible_contacts(self.request.user).order_by('-pk')
        term=self.request.query_params.get('search','').strip()[:250]
        if term:qs=qs.filter(Q(name__icontains=term)|Q(phone__icontains=term)|Q(email__icontains=term))
        status=self.request.query_params.get('status','')
        if status:qs=qs.filter(status=status)
        return qs

@api_view(['GET'])
def dashboard(request):
    qs=visible_contacts(request.user)
    tasks=FollowUpTask.objects.filter(closed_at__isnull=True)
    if request.user.role=='setter':tasks=tasks.filter(setter_id=request.user.pk)
    if request.user.role=='advisor':tasks=tasks.none()
    pending=Appointment.objects.filter(advisor_id=request.user.pk,status='scheduled',ends_at__lte=timezone.now(),report__isnull=True).count() if request.user.role=='advisor' else 0
    return Response({'workspace':'assurance','role':request.user.role,'contacts':qs.count(),
        'open_follow_ups':tasks.count(),'reports_due':pending,'stage':'contacts_import','available':['contacts','imports','locking','assignments','appointments'],'pending':['phonetico','calendars']})
