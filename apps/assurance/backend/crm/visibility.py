from django.db.models import Q, Exists, OuterRef
from .models import Contact, Appointment


def visible_contacts(user):
    qs = Contact.objects.all()
    if user.role == 'advisor':
        linked = Appointment.objects.filter(contact_id=OuterRef('pk'), advisor_id=user.pk)
        qs = qs.annotate(_linked_appointment=Exists(linked)).filter(
            Q(assigned_advisor_id=user.pk) | Q(_linked_appointment=True)
        )
    if user.role == 'setter':
        qs = qs.filter(assigned_setter_id=user.pk)
    return qs
