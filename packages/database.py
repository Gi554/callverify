"""Explicit per-service schema selection for a common PostgreSQL database."""

import os
from django.core.exceptions import ImproperlyConfigured


def configure_schema(database, service):
    schema = os.getenv('CRM_DB_SCHEMA', '')
    if not schema:
        return
    if schema != service or database['ENGINE'] != 'django.db.backends.postgresql':
        raise ImproperlyConfigured('CRM_DB_SCHEMA requires PostgreSQL and the service schema.')
    database.setdefault('OPTIONS', {})['options'] = '-c search_path=' + schema
