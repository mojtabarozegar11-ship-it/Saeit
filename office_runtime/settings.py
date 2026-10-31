"""Sidecar-only Django settings for /company/office/.

This module is intentionally separate from the existing public site's WSGI
entrypoint. Credentials and DATABASE_URL are loaded by config.settings from
the sidecar application root's private .env file.
"""
from config.settings import *  # noqa: F401,F403

ROOT_URLCONF = "office_runtime.urls"
WSGI_APPLICATION = "office_runtime.passenger_wsgi.application"
FORCE_SCRIPT_NAME = "/company/office"

# Keep the private-office session and CSRF cookies separate from public Django.
SESSION_COOKIE_NAME = "zm_office_sessionid"
SESSION_COOKIE_PATH = "/company/office/"
CSRF_COOKIE_NAME = "zm_office_csrftoken"
CSRF_COOKIE_PATH = "/company/office/"
LOGIN_URL = "/company/office/secure-login/"

# Do not overwrite the public site's static manifest.
STATIC_URL = "/company/office/static/"
STATIC_ROOT = BASE_DIR / "office-staticfiles"
