import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR=Path(__file__).resolve().parents[3]
DEBUG=os.getenv('DEBUG','false').lower()=='true'
ALLOWED_HOSTS=os.getenv('ALLOWED_HOSTS','localhost,127.0.0.1,testserver').split(',')
USE_TZ=True
TIME_ZONE='UTC'
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'

SECRET_KEY = os.getenv('ASSURANCE_SECRET_KEY','')
if not SECRET_KEY:
    if not DEBUG:raise ImproperlyConfigured('ASSURANCE_SECRET_KEY required')
    SECRET_KEY='local-assurance-development-only'
INSTALLED_APPS=['django.contrib.contenttypes','django.contrib.auth','rest_framework','apps.assurance.backend.crm']
MIDDLEWARE=['django.middleware.security.SecurityMiddleware','django.middleware.common.CommonMiddleware']
ROOT_URLCONF='apps.assurance.backend.urls'
DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'assurance.sqlite3'}}
if os.getenv('ASSURANCE_DB_HOST'):
    DATABASES['default']={'ENGINE':'django.db.backends.postgresql','HOST':os.environ['ASSURANCE_DB_HOST'],
        'NAME':os.getenv('ASSURANCE_DB_NAME','amx_assurance'),'USER':os.getenv('ASSURANCE_DB_USER','amx_assurance'),
        'PASSWORD':os.environ['ASSURANCE_DB_PASSWORD'],'PORT':os.getenv('ASSURANCE_DB_PORT','5432')}
REST_FRAMEWORK={'DEFAULT_AUTHENTICATION_CLASSES':['apps.assurance.backend.crm.access.WorkspaceAuthentication'],
    'DEFAULT_PERMISSION_CLASSES':['rest_framework.permissions.IsAuthenticated'],'UNAUTHENTICATED_USER':None}

PORTAL_INTERNAL_URL=os.getenv("PORTAL_INTERNAL_URL","http://127.0.0.1:8090" if DEBUG else "")
