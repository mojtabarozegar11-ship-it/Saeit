"""MOJ PROP standalone paid-assessment settings.

Separate customer/session/auth database from historical 16GB company MariaDB.
Will not start with missing private secret, unsafe file permissions or a public
database path. Both actual invoice release controls default to False.
"""
import os
from pathlib import Path
import stat

BASE_DIR=Path(__file__).resolve().parents[1]
db_raw=os.environ.get("MOJPROP_V141_LEDGER_PATH","")
if not db_raw or not Path(db_raw).is_absolute():
    raise RuntimeError("Standalone ledger absolute private path required")
DB_FILE=Path(db_raw)
if (DB_FILE.is_symlink() or not DB_FILE.is_file()
        or DB_FILE.parent.is_symlink() or not DB_FILE.parent.is_dir()):
    raise RuntimeError("Private merchant ledger missing or symlinked")
if (DB_FILE.stat().st_uid!=os.getuid()
        or DB_FILE.parent.stat().st_uid!=os.getuid()
        or stat.S_IMODE(DB_FILE.stat().st_mode)!=0o600
        or stat.S_IMODE(DB_FILE.parent.stat().st_mode)!=0o700):
    raise RuntimeError("Merchant ledger private owner/mode mismatch")
unsafe=(BASE_DIR,Path("/home/zomorod2/mojplaywin.com"),
        Path("/home/zomorod2/public_html"))
for root in unsafe:
    if DB_FILE==root or root in DB_FILE.parents:
        raise RuntimeError("Merchant ledger cannot reside inside app/public code root")
secret_path=DB_FILE.parent/"secret.key"
if (secret_path.is_symlink() or not secret_path.is_file()
        or stat.S_IMODE(secret_path.stat().st_mode)!=0o600
        or secret_path.stat().st_uid!=os.getuid()):
    raise RuntimeError("Production standalone Django signing secret unavailable")
SECRET_KEY=secret_path.read_text("utf8").strip()
if len(SECRET_KEY)<64:
    raise RuntimeError("Weak or missing private standalone signing key")

def flag(name):
    return os.environ.get(name,"0") == "1"

DEBUG=False
ALLOWED_HOSTS=["mojplaywin.com","www.mojplaywin.com"]
CSRF_TRUSTED_ORIGINS=["https://mojplaywin.com","https://www.mojplaywin.com"]
INSTALLED_APPS=[
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "prop_firm.apps.MojPropConfig",
]
MIDDLEWARE=[
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF="mojprop_isolated.urls"
WSGI_APPLICATION="mojprop_isolated.wsgi.application"
DATABASES={
    "default":{
        "ENGINE":"django.db.backends.sqlite3",
        "NAME":str(DB_FILE),
        "CONN_MAX_AGE":0,
        "OPTIONS":{"timeout":30,"transaction_mode":"IMMEDIATE"},
    },
}
DEFAULT_AUTO_FIELD="django.db.models.BigAutoField"
TEMPLATES=[{
    "BACKEND":"django.template.backends.django.DjangoTemplates",
    "DIRS":[BASE_DIR/"templates"],
    "APP_DIRS":True,
    "OPTIONS":{"context_processors":[
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
USE_TZ=True
TIME_ZONE="UTC"
LANGUAGE_CODE="en"
LOGIN_URL="/moj-prop-v141/login/"
LOGIN_REDIRECT_URL="/moj-prop-v141/"
SESSION_COOKIE_NAME="mojprop_v141_session"
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE="Strict"
SESSION_COOKIE_PATH="/moj-prop-v141/"
CSRF_COOKIE_NAME="mojprop_v141_csrf"
CSRF_COOKIE_SECURE=True
CSRF_COOKIE_SAMESITE="Strict"
CSRF_COOKIE_PATH="/moj-prop-v141/"
SECURE_SSL_REDIRECT=True
SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO","https")
SECURE_CONTENT_TYPE_NOSNIFF=True
SECURE_REFERRER_POLICY="no-referrer"
X_FRAME_OPTIONS="DENY"

# No customer-facing paid invoice before all operational evidence is verified.
MOJPROP_V141_NATIVE_TRX_RELEASE_ENABLED=flag("MOJPROP_V141_NATIVE_TRX_RELEASE_ENABLED")
MOJPROP_TRX_GLOBAL_LEDGER_RECONCILED=flag("MOJPROP_TRX_GLOBAL_LEDGER_RECONCILED")
MOJPROP_TRX_AUTORECONCILE_ENABLED=flag("MOJPROP_TRX_AUTORECONCILE_ENABLED")
MOJ_PROP_V141_PORTFOLIO_ENABLED=flag("MOJ_PROP_V141_PORTFOLIO_ENABLED")
MOJPROP_V141_TRON_RECEIVER=os.environ.get("MOJPROP_V141_TRON_RECEIVER","")
MOJPROP_V141_ORDER_SIGNING_KEY=os.environ.get("MOJPROP_V141_ORDER_SIGNING_KEY","")
MOJPROP_V141_NATIVE_TERMS_VERSION=os.environ.get("MOJPROP_V141_NATIVE_TERMS_VERSION","")
MOJPROP_V141_NATIVE_TERMS_SHA256=os.environ.get("MOJPROP_V141_NATIVE_TERMS_SHA256","")
MOJPROP_V141_TRON_SOLIDITY_PROVIDERS=tuple(
    x.strip() for x in os.environ.get("MOJPROP_V141_TRON_SOLIDITY_PROVIDERS","").split(",")
    if x.strip()
)
MOJPROP_V141_TRON_HISTORY_INDEXER=os.environ.get(
    "MOJPROP_V141_TRON_HISTORY_INDEXER","")
MOJPROP_V141_TRONGRID_API_KEY=os.environ.get(
    "MOJPROP_V141_TRONGRID_API_KEY","")
