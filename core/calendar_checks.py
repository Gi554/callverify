from packages.calendar_connectors.booking import check as shared_check, Busy
from packages.calendar_connectors.booking import Unavailable as Unavailable  # re-exported


def check(user, client, start, end, source_id=None):
    from .isolation_work import Conflict

    try:
        return shared_check(user, client, start, end, source_id, workspace='isolation')
    except Busy:
        raise Conflict('Créneau occupé dans l’agenda externe du client.') from None
