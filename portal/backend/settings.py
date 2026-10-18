"""Central identity service. No business CRM models are installed here."""
import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parents[2]
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
SECRET_KEY = os.getenv('PORTAL_SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('PORTAL_SECRET_KEY required')
    SECRET_KEY = 'local-portal-development-only'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS','localhost,127.0.0.1,testserver').split(',')
INSTALLED_APPS = ['django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions',
    'rest_framework','portal.backend.identity']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware']
ROOT_URLCONF = 'portal.backend.urls'
DATABASES = {'default':{'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'portal.sqlite3'}}
if os.getenv('PORTAL_DB_HOST'):
    DATABASES['default'] = {'ENGINE':'django.db.backends.postgresql','HOST':os.environ['PORTAL_DB_HOST'],
        'NAME':os.getenv('PORTAL_DB_NAME','amx_portal'),'USER':os.getenv('PORTAL_DB_USER','amx_portal'),
        'PASSWORD':os.environ['PORTAL_DB_PASSWORD'],'PORT':os.getenv('PORTAL_DB_PORT','5432')}
SESSION_COOKIE_NAME = 'amx_portal_session'
CSRF_COOKIE_NAME = 'amx_portal_csrf'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = 'Strict'
SESSION_COOKIE_AGE = 8 * 3600
if os.getenv('TRUST_PROXY','false').lower()=='true':
    SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO','https')
CSRF_TRUSTED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS','http://127.0.0.1:5173,http://localhost:5173').split(',')
USE_TZ = True
TIME_ZONE = 'UTC'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
REST_FRAMEWORK = {'DEFAULT_AUTHENTICATION_CLASSES':['rest_framework.authentication.SessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES':['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_THROTTLE_RATES':{'portal_login':'10/min','user':'120/min'}}
AUTH_PASSWORD_VALIDATORS = [
    {'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':12}},
    {'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'}]
