import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
SECRET_KEY = os.getenv('SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('SECRET_KEY required; set DEBUG=true for local development')
    SECRET_KEY = 'local-development-only-not-for-production'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
INSTALLED_APPS = ['django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'rest_framework', 'corsheaders', 'core']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','APP_DIRS':True,
    'OPTIONS':{'context_processors':['django.template.context_processors.request',
    'django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'config.wsgi.application'
AUTH_USER_MODEL = 'core.AdminUser'
DATABASES = {'default': {'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR / 'db.sqlite3'}}
if os.getenv('POSTGRES_HOST'):
    DATABASES = {'default': {'ENGINE':'django.db.backends.postgresql','NAME':os.getenv('POSTGRES_DB','callverify'),
        'USER':os.getenv('POSTGRES_USER','callverify'),'PASSWORD':os.environ['POSTGRES_PASSWORD'],
        'HOST':os.environ['POSTGRES_HOST'],'PORT':os.getenv('POSTGRES_PORT','5432')}}
AUTH_PASSWORD_VALIDATORS = [{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':12}},
    {'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'UTC'
USE_TZ = True
STATIC_URL = 'static/'
MEDIA_ROOT = BASE_DIR / 'private-media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
REST_FRAMEWORK = {'DEFAULT_AUTHENTICATION_CLASSES':['rest_framework.authentication.SessionAuthentication'],
    'DEFAULT_FILTER_BACKENDS':['rest_framework.filters.SearchFilter'],
    'DEFAULT_PERMISSION_CLASSES':['core.permissions.AdminOnly'],
    'DEFAULT_PAGINATION_CLASS':'core.pagination.Pagination','PAGE_SIZE':25,
    'DEFAULT_THROTTLE_CLASSES':['rest_framework.throttling.UserRateThrottle'],
    'DEFAULT_THROTTLE_RATES':{'user':'120/min','login':'10/min'}}
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS','http://localhost:5173,http://127.0.0.1:5173,http://127.0.0.1:8080').split(',')
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_CONTENT_TYPE_NOSNIFF = True
if os.getenv('TRUST_PROXY','false').lower()=='true':
    SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO','https')
CELERY_BROKER_URL = os.getenv('REDIS_URL','redis://localhost:6379/0')
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_EAGER','false').lower() == 'true'
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_TIME_LIMIT = 1800
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
MAX_IMPORT_BYTES = 20 * 1024 * 1024
MAX_IMPORT_ROWS = 100000
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID','')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN','')
VOICE_ENABLED = False  # No environment flag can enable outbound calls yet.
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', '')
VOICE_CALLBACK_URL = os.getenv('VOICE_CALLBACK_URL', '')
LOOKUP_ENABLED = os.getenv('LOOKUP_ENABLED','false').lower() == 'true'
LOOKUP_CACHE_HOURS = 168
LOOKUP_UNIT_COST = os.getenv('LOOKUP_UNIT_COST','0.01')
VOICE_ENABLED = False  # Activation requires the separate production compliance implementation.
MFA_ENCRYPTION_KEY = os.getenv('MFA_ENCRYPTION_KEY','')
if not DEBUG and not MFA_ENCRYPTION_KEY:
    raise ImproperlyConfigured('MFA_ENCRYPTION_KEY required in production')
LOOKUP_PACKAGES = os.getenv('LOOKUP_PACKAGES','')
if set(filter(None,LOOKUP_PACKAGES.split(',')))-{'line_type_intelligence','line_status'}:
    raise ImproperlyConfigured('Unsupported LOOKUP_PACKAGES')
CELERY_BEAT_SCHEDULE = {
    'dispatch-outbox':{'task':'core.tasks.dispatch_task','schedule':30.0},
    'purge-expired-files':{'task':'core.tasks.purge_task','schedule':3600.0}}
if os.getenv('REDIS_CACHE_URL'):
    CACHES = {'default':{'BACKEND':'django.core.cache.backends.redis.RedisCache','LOCATION':os.environ['REDIS_CACHE_URL']}}
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND','django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST','localhost')
EMAIL_PORT = int(os.getenv('EMAIL_PORT','587'))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER','')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD','')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL','callverify@localhost')
FRONTEND_URL = os.getenv('FRONTEND_URL','http://127.0.0.1:5173')
PASSWORD_RESET_TIMEOUT = 3600
if os.getenv('S3_BUCKET'):
    STORAGES = {
        'default': {'BACKEND':'storages.backends.s3.S3Storage', 'OPTIONS':{
            'bucket_name':os.environ['S3_BUCKET'], 'region_name':os.getenv('AWS_REGION','ca-central-1'),
            'endpoint_url':os.getenv('S3_ENDPOINT_URL') or None,
            'default_acl':None, 'querystring_auth':True, 'file_overwrite':False,
            'object_parameters':{'ServerSideEncryption':'AES256'}}},
        'staticfiles': {'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}}
