"""Appointments booked per advisor: each non-cancelled one consumes a unit of the advisor's quota."""

from django.db.models import Count
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Appointment


@api_view(['GET'])
def usage(request):
    rows = (
        Appointment.objects.exclude(status='cancelled')
        .values('advisor_id')
        .annotate(booked=Count('pk'))
        .order_by('advisor_id')
    )
    response = Response({'results': [dict(row) for row in rows]})
    response['Cache-Control'] = 'no-store'
    return response
