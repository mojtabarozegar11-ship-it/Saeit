from pathlib import Path

try:
    import environ
except ModuleNotFoundError as error:
    if error.name != "environ":
        raise
    from config import env_compat as environ

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="change-me")
DEBUG = env("DEBUG")

if not DEBUG and SECRET_KEY == "change-me":
    raise RuntimeError("SECRET_KEY must be configured when DEBUG=False")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

if not DEBUG and not ALLOWED_HOSTS:
    raise RuntimeError("ALLOWED_HOSTS must contain at least one host when DEBUG=False")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "core",
    "farnaz.apps.FarnazConfig",
    "command_center",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.RequestAuditMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        }
    }
]

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "fa-ir"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
APP_VERSION = env("APP_VERSION", default="0.1.0")
PAYMENT_WEBHOOK_SECRET = env("PAYMENT_WEBHOOK_SECRET", default="")

# Company international trade mailbox. Credentials remain in environment/.env only.
COMPANY_TRADE_EMAIL = env("COMPANY_TRADE_EMAIL", default="")
TRADE_EMAIL_ENABLED = env.bool("TRADE_EMAIL_ENABLED", default=False)
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default=COMPANY_TRADE_EMAIL)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.BasicAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly"
    ]
}

# cPanel/Passenger deployments commonly terminate TLS at the web server.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT", default=False)
SESSION_COOKIE_SECURE = env("SESSION_COOKIE_SECURE", default=not DEBUG)
CSRF_COOKIE_SECURE = env("CSRF_COOKIE_SECURE", default=not DEBUG)
SECURE_HSTS_SECONDS = env("SECURE_HSTS_SECONDS", default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
SECURE_HSTS_PRELOAD = env("SECURE_HSTS_PRELOAD", default=False)
# Production-safe defaults. HSTS and HTTPS redirects are only enforced at
# the separately verified cPanel TLS termination layer.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"


# Crown Defender — fail-closed dedicated native TRX checkout (NOT USDT).
# All financial release switches are false until documented mainnet acceptance.
# Never put keys, wallet seeds, or customer payment data in GitHub.
CROWN_STORE_ENABLED = env.bool("CROWN_STORE_ENABLED", default=False)
CROWN_PAYMENT_GATEWAY_APPROVED = env.bool("CROWN_PAYMENT_GATEWAY_APPROVED", default=False)
CROWN_TRX_INDEPENDENT_OPERATORS_REVIEWED = env.bool(
    "CROWN_TRX_INDEPENDENT_OPERATORS_REVIEWED", default=False)
CROWN_TRX_DEDICATED_RECEIVER_ATTESTED = env.bool(
    "CROWN_TRX_DEDICATED_RECEIVER_ATTESTED", default=False)
CROWN_TRX_PAID_END_TO_END_ACCEPTED = env.bool(
    "CROWN_TRX_PAID_END_TO_END_ACCEPTED", default=False)
CROWN_TRX_MERCHANT_RECEIVER = env("CROWN_TRX_MERCHANT_RECEIVER", default="")
CROWN_TRX_AUTO_DISCOVERY_ENABLED = env.bool("CROWN_TRX_AUTO_DISCOVERY_ENABLED", default=False)
CROWN_TRX_INDEXER_KEY = env("CROWN_TRX_INDEXER_KEY", default="")
CROWN_TRX_RPC_PROVIDERS = [
    {"source_id": "crown_rpc_a", "operator_id": env("CROWN_TRX_RPC_A_OPERATOR", default=""),
     "endpoint": env("CROWN_TRX_RPC_A_ORIGIN", default=""),
     "api_key": env("CROWN_TRX_RPC_A_KEY", default=""),
     "api_key_header": env("CROWN_TRX_RPC_A_KEY_HEADER", default="TRON-PRO-API-KEY")},
    {"source_id": "crown_rpc_b", "operator_id": env("CROWN_TRX_RPC_B_OPERATOR", default=""),
     "endpoint": env("CROWN_TRX_RPC_B_ORIGIN", default=""),
     "api_key": env("CROWN_TRX_RPC_B_KEY", default=""),
     "api_key_header": env("CROWN_TRX_RPC_B_KEY_HEADER", default="X-API-KEY")},
]
from services.mpw_crown_price_quotes import (
    coingecko_usd_per_trx as CROWN_TRX_RATE_SOURCE_A,
    kraken_usd_per_trx as CROWN_TRX_RATE_SOURCE_B,
)
