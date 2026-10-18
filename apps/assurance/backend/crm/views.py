from rest_framework import serializers,viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Contact

class PublicContactSerializer(serializers.ModelSerializer):
    # Deliberate allowlist: no setter identity, creator or actor metadata.
    class Meta:
        model=Contact
        fields=['id','name','phone','email','status','updated_at']
        read_only_fields=['status','updated_at']

class ContactViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class=PublicContactSerializer
    http_method_names=['get','head','options']
    def get_queryset(self):
        qs=Contact.objects.order_by('-pk')
        if self.request.user.role=='advisor':qs=qs.filter(assigned_advisor_id=self.request.user.pk)
        return qs

@api_view(['GET'])
def dashboard(request):
    qs=Contact.objects.all()
    if request.user.role=='advisor':qs=qs.filter(assigned_advisor_id=request.user.pk)
    return Response({'workspace':'assurance','role':request.user.role,'contacts':qs.count(),
        'stage':'foundation','available':['contacts'],'pending':['locking','phonetico','appointments','tasks','calendars']})
