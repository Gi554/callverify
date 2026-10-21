from packages.calendar_connectors.booking import check as shared_check,Unavailable,Busy
from .leases import Conflict

def check(user,advisor,start,end,source_id=None):
    try:return shared_check(user,advisor,start,end,source_id)
    except Busy:raise Conflict('Créneau occupé dans l’agenda externe du conseiller.') from None
