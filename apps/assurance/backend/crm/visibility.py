from django.db.models import Q, Exists, OuterRef
from .models import Contact, Appointment


def visible_contacts(user):
    qs = Contact.objects.all()
    if user.role == 'advisor':
        linked = Appointment.objects.filter(contact_id=OuterRef('pk'), advisor_id=user.pk)
        qs = qs.annotate(_linked_appointment=Exists(linked)).filter(
            Q(assigned_advisor_id=user.pk) | Q(_linked_appointment=True)
        )
    # Until the first lot is handed out the team shares one pool, as before; afterwards each
    # setter works only the prospects of their own lot.
    if user.role == 'setter' and Contact.objects.filter(assigned_setter_id__isnull=False).exists():
        # Own lot, plus the files the setter created themselves (numbers dialed by hand).
        qs = qs.filter(Q(assigned_setter_id=user.pk) | Q(created_by_id=user.pk))
    return qs
