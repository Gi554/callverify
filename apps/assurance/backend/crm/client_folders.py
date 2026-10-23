from rest_framework.decorators import api_view
from packages.client_folders import folders
from packages.client_folder_export import export


@api_view(['GET'])
def clients(request, client_id=None):
    return folders(request, 'assurance', client_id)


@api_view(['GET'])
def export_client(request, client_id):
    return export(request, 'assurance', client_id)
