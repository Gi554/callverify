"""Only confirmed attendance consumes the advisor's prospect quota."""

from django.db.models import Count, Q, OuterRef, Subquery
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from .models import Appointment, Contact


def appointment_usage(user):
    rows = Appointment.objects.exclude(status='cancelled')
    if user.role == 'advisor':
        rows = rows.filter(advisor_id=user.pk)
    return rows


@api_view(['GET'])
def usage(request):
    rows = (
        appointment_usage(request.user)
        .values('advisor_id')
        .annotate(
            booked=Count('pk'),
            attended=Count('pk', filter=Q(report__performed=True)),
            absent=Count('pk', filter=Q(report__performed=False, report__outcome='absent')),
        )
        .order_by('advisor_id')
    )
    response = Response({'results': [dict(row) for row in rows]})
    response['Cache-Control'] = 'no-store'
    return response


@api_view(['GET'])
def prospects(request):
    if request.user.role != 'advisor':
        raise PermissionDenied('Liste personnelle réservée au conseiller.')
    own = Appointment.objects.filter(advisor_id=request.user.pk)
    rows = (
        Contact.objects.filter(
            Q(assigned_advisor_id=request.user.pk)
            | Q(assigned_advisor_id__isnull=True, appointments__advisor_id=request.user.pk)
        )
        .distinct()
        .annotate(
            appointment_id=Subquery(
                own.filter(contact_id=OuterRef('pk')).order_by('-starts_at', '-pk').values('pk')[:1]
            ),
            attended=Count(
                'appointments',
                filter=Q(
                    appointments__advisor_id=request.user.pk,
                    appointments__status='scheduled',
                    appointments__report__performed=True,
                ),
                distinct=True,
            ),
        )
    )
    totals = appointment_usage(request.user).aggregate(
        attended=Count('pk', filter=Q(report__performed=True)),
        absent=Count('pk', filter=Q(report__performed=False, report__outcome='absent')),
    )
    totals['assigned'] = rows.count()
    term = request.query_params.get('search', '').strip()[:250]
    if term:
        rows = rows.filter(
            Q(name__icontains=term) | Q(phone__icontains=term) | Q(email__icontains=term)
        )
    paginator = PageNumberPagination()
    paginator.page_size = 25
    page = paginator.paginate_queryset(rows.order_by('-updated_at', '-pk'), request)
    response = paginator.get_paginated_response(
        [
            {
                key: getattr(row, key)
                for key in ('id', 'name', 'phone', 'email', 'appointment_id', 'attended')
            }
            for row in page
        ]
    )
    response.data['totals'] = totals
    response['Cache-Control'] = 'no-store'
    return response
