"""
Production settings for Expense Tracking & Management System.
"""

import os
from pathlib import Path
from .base import *

DEBUG = False

# Strict host headers in production (comma-separated list in env)
# Automatically handles wildcard syntax like *.onrender.com by converting to Django's .onrender.com
raw_allowed_hosts = [host.strip() for host in os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',') if host.strip()]
ALLOWED_HOSTS = []
for h in raw_allowed_hosts:
    if h.startswith('*.'):
        ALLOWED_HOSTS.append(h[1:])  # Convert *.onrender.com -> .onrender.com
    else:
        ALLOWED_HOSTS.append(h)
if '.onrender.com' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('.onrender.com')

# CSRF Trusted Origins for reverse proxy & custom domain integration
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]
if 'https://*.onrender.com' not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append('https://*.onrender.com')

# Reverse Proxy SSL Header Configuration
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Production Static and Media Roots
STATIC_ROOT = Path(os.getenv('STATIC_ROOT', str(BASE_DIR / 'staticfiles')))
MEDIA_ROOT = Path(os.getenv('MEDIA_ROOT', str(BASE_DIR / 'media')))

# WhiteNoise production static asset storage with compression and cache headers
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Production MySQL Database Configuration
from typing import Any

DB_OPTIONS: dict[str, Any] = {
    'charset': 'utf8mb4',
    'init_command': "SET sql_mode='STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION'",
}

# Cloud MySQL (TiDB Cloud, AWS RDS, etc.) SSL support
if os.getenv('DB_SSL', 'False').lower() in ('true', '1', 't') or os.getenv('DB_PORT') == '4000':
    ca_path = os.getenv('DB_SSL_CA', '/etc/ssl/certs/ca-certificates.crt')
    if os.path.exists(ca_path):
        DB_OPTIONS['ssl'] = {'ca': ca_path}
    else:
        DB_OPTIONS['ssl'] = {'ssl_mode': 'REQUIRED'}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', '127.0.0.1'),
        'PORT': os.getenv('DB_PORT', '3306'),
        'OPTIONS': DB_OPTIONS,
        'CONN_MAX_AGE': int(os.getenv('DB_CONN_MAX_AGE', '600')),
    }
}

# Production Security Headers & Cookie Policies
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'True').lower() in ('true', '1', 't')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # Allows JS/HTMX AJAX to read token from cookie if needed

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# HSTS Configuration (HTTP Strict Transport Security)
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000'))  # 1 year default
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Production Email & Error Notification Settings
ADMINS_ENV = os.getenv('ADMINS', '')
ADMINS = [
    (item.split(':')[0].strip(), item.split(':')[1].strip())
    for item in ADMINS_ENV.split(';')
    if ':' in item
]
MANAGERS = ADMINS

EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 't')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@yourdomain.com')
SERVER_EMAIL = os.getenv('SERVER_EMAIL', DEFAULT_FROM_EMAIL)

# Production Logging with Size-based Rotation
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} [{name}:{lineno}] {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'financial_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOGS_DIR / 'financial.log'),
            'maxBytes': 10 * 1024 * 1024,  # 10 MB per file
            'backupCount': 10,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOGS_DIR / 'security.log'),
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 10,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOGS_DIR / 'errors.log'),
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 10,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': True,
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'error_file'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['error_file', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'expense_tracking.financial': {
            'handlers': ['console', 'financial_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'expense_tracking.security': {
            'handlers': ['console', 'security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'expense_tracking.errors': {
            'handlers': ['console', 'error_file', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
