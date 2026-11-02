from rest_framework.decorators import api_view
from packages.setter_performance import performance
from .admin_alerts import Store as AlertStore


class Store(AlertStore):
    snapshot = 'qualification_snapshot'

    @staticmethod
    def money_sources(agent):
        from django.utils import timezone

        return [
            (
                Store.Meeting.objects.filter(
                    setter_id=agent,
                    status='scheduled',
                    report__performed=True,
                    ends_at__lte=timezone.now(),
                ),
                'report__unit_rate_cad',
            )
        ]


@api_view(['GET'])
def own(request, agent=None):
    return performance(Store, request, agent)
