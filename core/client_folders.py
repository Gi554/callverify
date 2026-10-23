from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from packages.client_folders import folders
from packages.client_folder_export import export
from .isolation_work import WorkAuthentication


@api_view(['GET'])
@authentication_classes([WorkAuthentication])
@permission_classes([IsAuthenticated])
def clients(request, client_id=None):
    return folders(request, 'isolation', client_id)


@api_view(['GET'])
@authentication_classes([WorkAuthentication])
@permission_classes([IsAuthenticated])
def export_client(request, client_id):
    return export(request, 'isolation', client_id)
