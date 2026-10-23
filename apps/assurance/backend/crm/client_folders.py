from rest_framework.decorators import api_view
from packages.client_folders import folders


@api_view(['GET'])
def clients(request, client_id=None):
    return folders(request, 'assurance', client_id)
