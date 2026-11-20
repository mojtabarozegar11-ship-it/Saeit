"""Dedicated MOJ PROP runtime configuration, never import shared site settings.

Only one database alias, pinned to the provisioned independent schema.
No shared auth/session cookie or shared database fallback.
Commercial capabilities remain disabled until separately reviewed evidence
and operational provider configuration are integrated.
"""
import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR=Path(__file__).resolve().parent.parent
DEDICATED_DB="zomorod2_mojprop"
def required(name):
    value=os.environ.get(name,"")
    if not value.strip():
        raise ImproperlyConfigured("Missing dedicated MOJ PROP configuration: "+name)
    return value
SECRET_KEY=required("MOJ_PROP_SECRET_KEY")
if len(SECRET_KEY)<50:
    raise ImproperlyConfigured("Dedicated secret key is too short")
db_name=required("MOJ_PROP_DB_NAME")
db_user=required("MOJ_PROP_DB_USER")
if db_name!=DEDICATED_DB:
    raise ImproperlyConfigured("Only the dedicated MOJ PROP database is permitted")
if not db_user.startswith("zomorod2_") or db_user in {"zomorod2_sites_admin","zomorod2_root"}:
    raise ImproperlyConfigured("A separate least-privilege database principal is required")
DATABASES={"default":{"ENGINE":"django.db.backends.mysql","NAME":db_name,
    "USER":db_user,"PASSWORD":required("MOJ_PROP_DB_PASSWORD"),
    "HOST":"localhost","PORT":"3306",
    "OPTIONS":{"charset":"utf8mb4","init_command":"SET sql_mode='STRICT_TRANS_TABLES'"},
    "CONN_MAX_AGE":0}}
DATABASE_ROUTERS=[]
DEBUG=False
ALLOWED_HOSTS=["mojplaywin.com"]
CSRF_TRUSTED_ORIGINS=["https://mojplaywin.com"]
ROOT_URLCONF="config.mojprop_urls"
WSGI_APPLICATION="config.mojprop_wsgi.application"
# Passenger must mount at /moj-prop and provide stripped PATH_INFO.
FORCE_SCRIPT_NAME="/moj-prop"
APPEND_SLASH=True
INSTALLED_APPS=["django.contrib.auth","django.contrib.contenttypes",
    "django.contrib.sessions","django.contrib.staticfiles","prop_firm.apps.MojPropConfig"]
MIDDLEWARE=["django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware","django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware","django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware"]
TEMPLATES=[{"BACKEND":"django.template.backends.django.DjangoTemplates",
    "DIRS":[BASE_DIR/"prop_firm"/"isolated_templates",BASE_DIR/"core"/"templates"],
    "APP_DIRS":True,"OPTIONS":{"context_processors":[
        "django.template.context_processors.request","django.contrib.auth.context_processors.auth"]}}]
AUTH_USER_MODEL="auth.User"
AUTHENTICATION_BACKENDS=["django.contrib.auth.backends.ModelBackend"]
DEFAULT_AUTO_FIELD="django.db.models.BigAutoField"
LANGUAGE_CODE="en-us"
TIME_ZONE="UTC"
USE_I18N=True
USE_TZ=True
SESSION_ENGINE="django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME="mojprop_session_v1"
CSRF_COOKIE_NAME="mojprop_csrf_v1"
SESSION_COOKIE_PATH=CSRF_COOKIE_PATH="/moj-prop/"
SESSION_COOKIE_DOMAIN=CSRF_COOKIE_DOMAIN=None
SESSION_COOKIE_SECURE=CSRF_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=CSRF_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=CSRF_COOKIE_SAMESITE="Lax"
SECURE_SSL_REDIRECT=True
SECURE_CONTENT_TYPE_NOSNIFF=True
X_FRAME_OPTIONS="DENY"
SECURE_REFERRER_POLICY="same-origin"
# Do not trust forwarded HTTPS headers from an unverified edge.
STATIC_URL="/moj-prop/static/"
STATIC_ROOT=BASE_DIR/"mojprop-static-collected"
STATICFILES_DIRS=[BASE_DIR/"core"/"static"]
DATA_UPLOAD_MAX_MEMORY_SIZE=8192
DATA_UPLOAD_MAX_NUMBER_FIELDS=64
EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST=os.environ.get("MOJ_PROP_SMTP_HOST","")
EMAIL_HOST_USER=os.environ.get("MOJ_PROP_SMTP_USER","")
EMAIL_HOST_PASSWORD=os.environ.get("MOJ_PROP_SMTP_PASSWORD","")
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_TIMEOUT=10
MPW_SIMULATION_FROM_EMAIL=os.environ.get("MOJ_PROP_FROM_EMAIL","")
# Explicitly closed until production-grade shared throttle, licensed feed,
# independent settlement, terms and reserve approval are configured.
MPW_SIMULATION_IDENTITY_ENABLED=False
MPW_SIMULATION_CHECKOUT_ENABLED=False
MPW_SIMULATION_RECONCILIATION_ENABLED=False
MPW_SIMULATION_TRADING_ENABLED=False
MPW_SIMULATION_WORKER_READY=False
MPW_MOJPROP_PLAN1_ROUTE_ENABLED=False
MPW_MOJPROP_PLAN1_LIVE_INVOICE_ENABLED=False
MOJPROP_ISOLATED_RUNTIME=True
