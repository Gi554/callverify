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
REST_FRAMEWORK = {'DEFAULT_AUTHENTICATION_CLASSES':['portal.backend.identity.authentication.CentralSessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES':['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_THROTTLE_RATES':{'portal_login':'10/min','portal_password':'5/min','user':'120/min'}}
AUTH_PASSWORD_VALIDATORS = [
    {'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':12}},
    {'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'}]

# Portal mail settings are separate from the legacy Isolation mail transport.
PORTAL_PUBLIC_URL=os.getenv('PORTAL_PUBLIC_URL','http://127.0.0.1:5173' if DEBUG else '')
EMAIL_BACKEND=os.getenv('PORTAL_EMAIL_BACKEND','django.core.mail.backends.filebased.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_FILE_PATH=BASE_DIR/'private-media'/'portal-mail'
EMAIL_HOST=os.getenv('PORTAL_EMAIL_HOST','')
EMAIL_PORT=int(os.getenv('PORTAL_EMAIL_PORT','587'))
EMAIL_HOST_USER=os.getenv('PORTAL_EMAIL_USER','')
EMAIL_HOST_PASSWORD=os.getenv('PORTAL_EMAIL_PASSWORD','')
EMAIL_USE_TLS=os.getenv('PORTAL_EMAIL_TLS','true').lower()=='true'
EMAIL_TIMEOUT=10
PORTAL_MAIL_KEY=os.getenv('PORTAL_MAIL_KEY','')
ASSURANCE_INTERNAL_URL=os.getenv('ASSURANCE_INTERNAL_URL','http://127.0.0.1:8091' if DEBUG else 'http://assurance:8000')
if not DEBUG and not PORTAL_MAIL_KEY:raise ImproperlyConfigured('PORTAL_MAIL_KEY required')
DEFAULT_FROM_EMAIL=os.getenv('PORTAL_FROM_EMAIL','AMX <amx@localhost>')
PASSWORD_RESET_TIMEOUT=1800
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].update(portal_recovery='5/hour',portal_reset='10/hour')
PORTAL_CALENDAR_KEY=os.getenv('PORTAL_CALENDAR_KEY','')
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['portal_calendar']='20/min'
GOOGLE_CALENDAR_CLIENT_ID=os.getenv('GOOGLE_CALENDAR_CLIENT_ID','')
GOOGLE_CALENDAR_CLIENT_SECRET=os.getenv('GOOGLE_CALENDAR_CLIENT_SECRET','')
MICROSOFT_CALENDAR_CLIENT_ID=os.getenv('MICROSOFT_CALENDAR_CLIENT_ID','')
MICROSOFT_CALENDAR_CLIENT_SECRET=os.getenv('MICROSOFT_CALENDAR_CLIENT_SECRET','')
MICROSOFT_CALENDAR_TENANT=os.getenv('MICROSOFT_CALENDAR_TENANT','common')
ISOLATION_INTERNAL_URL=os.getenv('ISOLATION_INTERNAL_URL','http://127.0.0.1:8000' if DEBUG else 'http://api:8000')

NEWT_DIRECTORY_ENABLED=os.getenv('NEWT_DIRECTORY_ENABLED','false').lower()=='true'
NEWT_USERNAME=os.getenv('NEWT_USERNAME','')
NEWT_PASSWORD=os.getenv('NEWT_PASSWORD','')
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['phone_directory']='5/min'

NEWT_STATUS_ENABLED=os.getenv('NEWT_STATUS_ENABLED','false').lower()=='true'

NEWT_CDR_SCHEMA_ENABLED=os.getenv('NEWT_CDR_SCHEMA_ENABLED','false').lower()=='true'
NEWT_CDR_HISTORY_ENABLED=os.getenv('NEWT_CDR_HISTORY_ENABLED','false').lower()=='true'
NEWT_CALLS_ENABLED=os.getenv('NEWT_CALLS_ENABLED','false').lower()=='true'
NEWT_ISOLATION_CALLS_ENABLED=os.getenv('NEWT_ISOLATION_CALLS_ENABLED','false').lower()=='true'
