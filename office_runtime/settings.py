"""Sidecar-only Django settings for /company/office/.

This module is intentionally separate from the existing public site's WSGI
entrypoint. Credentials and DATABASE_URL are loaded by config.settings from
the sidecar application root's private .env file.
"""
import os
import re

from config.settings import *  # noqa: F401,F403

# A temporary, independently mounted route can be smoke-tested before cutover.
OFFICE_BASE_PATH = os.environ.get("ZM_OFFICE_BASE_PATH", "/company/office")
if OFFICE_BASE_PATH != "/company/office" and not re.fullmatch(
    r"/company/office-preflight-[0-9a-f]{12}", OFFICE_BASE_PATH
):
    raise RuntimeError("Invalid private-office mount path")

ROOT_URLCONF = "office_runtime.urls"
WSGI_APPLICATION = "office_runtime.passenger_wsgi.application"
FORCE_SCRIPT_NAME = OFFICE_BASE_PATH

# Keep the private-office session and CSRF cookies separate from public Django.
SESSION_COOKIE_NAME = "zm_office_sessionid"
SESSION_COOKIE_PATH = OFFICE_BASE_PATH + "/"
CSRF_COOKIE_NAME = "zm_office_csrftoken"
CSRF_COOKIE_PATH = OFFICE_BASE_PATH + "/"
LOGIN_URL = OFFICE_BASE_PATH + "/secure-login/"

# Do not overwrite the public site's static manifest.
STATIC_URL = OFFICE_BASE_PATH + "/static/"
STATIC_ROOT = BASE_DIR / "office-staticfiles"
