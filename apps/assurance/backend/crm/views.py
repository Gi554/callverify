from rest_framework import serializers,viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Contact
from .leases import ContactLeaseMixin
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination

class ContactPagination(PageNumberPagination):
    page_size=25

class PublicContactSerializer(serializers.ModelSerializer):
    # Deliberate allowlist: no setter identity, creator or actor metadata.
    class Meta:
        model=Contact
        fields=['id','name','phone','email','status','updated_at','revision']
        read_only_fields=['status','updated_at','revision']

class ContactViewSet(ContactLeaseMixin,viewsets.ReadOnlyModelViewSet):
    pagination_class=ContactPagination
    serializer_class=PublicContactSerializer
    http_method_names=['get','head','options','post','patch','delete']
    def get_queryset(self):
        qs=Contact.objects.order_by('-pk')
        if self.request.user.role=='advisor':qs=qs.filter(assigned_advisor_id=self.request.user.pk)
        term=self.request.query_params.get('search','').strip()[:250]
        if term:qs=qs.filter(Q(name__icontains=term)|Q(phone__icontains=term)|Q(email__icontains=term))
        return qs

@api_view(['GET'])
def dashboard(request):
    qs=Contact.objects.all()
    if request.user.role=='advisor':qs=qs.filter(assigned_advisor_id=request.user.pk)
    return Response({'workspace':'assurance','role':request.user.role,'contacts':qs.count(),
        'stage':'contacts_import','available':['contacts','imports','locking','assignments'],'pending':['phonetico','appointments','tasks','calendars']})
