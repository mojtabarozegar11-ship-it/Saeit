"""Fail-closed, dedicated MOJ Pay Django settings. Never use shared site settings.

This module is intentionally not activated by the existing static-site deploy.
Provision a distinct database and server-side secrets through cPanel or an
approved secret manager; do not store them in GitHub or page source.
"""
import os

from django.core.exceptions import ImproperlyConfigured


def _required(name):
    value = os.getenv(name, "")
    if not value:
        raise ImproperlyConfigured(name + " must be provisioned for the isolated service.")
    return value


SECRET_KEY = _required("BANKNEW_DJANGO_SECRET_KEY")
if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith("django-insecure-"):
    raise ImproperlyConfigured("BANKNEW_DJANGO_SECRET_KEY must be strong.")
DEBUG = False
ALLOWED_HOSTS = ["mojplaywin.com"]
ROOT_URLCONF = "banknew.isolated_urls"
WSGI_APPLICATION = "banknew.isolated_wsgi.application"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "banknew",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": _required("BANKNEW_DB_NAME"),
        "USER": _required("BANKNEW_DB_USER"),
        "PASSWORD": _required("BANKNEW_DB_PASSWORD"),
        "HOST": os.getenv("BANKNEW_DB_HOST", "localhost"),
        "PORT": os.getenv("BANKNEW_DB_PORT", "3306"),
        "CONN_MAX_AGE": 0,
        "OPTIONS": {"charset": "utf8mb4"},
    }
}
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "mojpay_session"
CSRF_COOKIE_NAME = "mojpay_csrf"
SESSION_COOKIE_PATH = "/banknew-api/"
CSRF_COOKIE_PATH = "/banknew-api/"
SESSION_COOKIE_DOMAIN = None
CSRF_COOKIE_DOMAIN = None
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 3600
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = False
CSRF_TRUSTED_ORIGINS = ["https://mojplaywin.com"]
SECURE_SSL_REDIRECT = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "no-referrer"
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_MEMORY_SIZE = 32768
FILE_UPLOAD_MAX_MEMORY_SIZE = 0
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
