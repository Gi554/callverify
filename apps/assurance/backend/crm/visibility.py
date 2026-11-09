from django.db.models import Q, Exists, OuterRef
from .models import Contact, Appointment


def visible_contacts(user):
    qs = Contact.objects.all()
    if user.role == 'advisor':
        linked = Appointment.objects.filter(contact_id=OuterRef('pk'), advisor_id=user.pk)
        qs = qs.annotate(_linked_appointment=Exists(linked)).filter(
            Q(assigned_advisor_id=user.pk) | Q(_linked_appointment=True)
        )
    # Once lots are in use, setters are limited to their own lot plus files they created
    # themselves. Before lot distribution starts, legacy direct-call flows may still use the
    # shared pool; the dashboard and UI list apply the setter-only counter/scope explicitly.
    if user.role == 'setter' and Contact.objects.filter(assigned_setter_id__isnull=False).exists():
        qs = qs.filter(Q(assigned_setter_id=user.pk) | Q(created_by_id=user.pk))
    return qs
