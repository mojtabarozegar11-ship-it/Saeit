from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="change-me")
DEBUG = env("DEBUG")
SAEIT_ENV = env("SAEIT_ENV", default="development").strip().lower()
if SAEIT_ENV not in {"development", "test", "ci", "staging", "production"}:
    raise RuntimeError("SAEIT_ENV must explicitly identify development, test, ci, staging, or production")

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

DATABASE_URL = env("DATABASE_URL", default="")
if SAEIT_ENV == "staging" and not DATABASE_URL:
    raise RuntimeError("Staging requires an explicit isolated DATABASE_URL; fallback databases are forbidden")
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
}
STAGING_DB_IDENTITY = env("STAGING_DB_IDENTITY", default="")
PRODUCTION_DB_IDENTITY = env("PRODUCTION_DB_IDENTITY", default="")
if SAEIT_ENV == "staging":
    if DEBUG or DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
        raise RuntimeError("Staging requires DEBUG=False and PostgreSQL")
    db_name = str(DATABASES["default"].get("NAME") or "")
    if not STAGING_DB_IDENTITY or STAGING_DB_IDENTITY != db_name:
        raise RuntimeError("Staging DATABASE_URL must match STAGING_DB_IDENTITY")
    if not PRODUCTION_DB_IDENTITY or PRODUCTION_DB_IDENTITY == db_name:
        raise RuntimeError("Staging must never select the production database identity")

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

# Public receiving addresses only; these settings do not prove blockchain settlement.
MOJPLAYWIN_TRON_RECEIVE_ADDRESS = env("MOJPLAYWIN_TRON_RECEIVE_ADDRESS", default="")
MOJPLAYWIN_ETHEREUM_RECEIVE_ADDRESS = env("MOJPLAYWIN_ETHEREUM_RECEIVE_ADDRESS", default="")
MOJPLAYWIN_CRYPTO_CHECKOUT_ENABLED = env.bool("MOJPLAYWIN_CRYPTO_CHECKOUT_ENABLED", default=False)


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
SESSION_COOKIE_SECURE = env("SESSION_COOKIE_SECURE", default=False)
CSRF_COOKIE_SECURE = env("CSRF_COOKIE_SECURE", default=False)
SECURE_HSTS_SECONDS = env("SECURE_HSTS_SECONDS", default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
SECURE_HSTS_PRELOAD = env("SECURE_HSTS_PRELOAD", default=False)

# Explicit external-action boundaries. Staging is always fail-closed.
PRODUCTION_PUBLICATION_ENABLED = env.bool("PRODUCTION_PUBLICATION_ENABLED", default=False)
REAL_PAYMENTS_ENABLED = env.bool("REAL_PAYMENTS_ENABLED", default=False)
TREASURY_EXECUTION_ENABLED = env.bool("TREASURY_EXECUTION_ENABLED", default=False)
CRYPTO_EXECUTION_ENABLED = env.bool("CRYPTO_EXECUTION_ENABLED", default=False)
FACTORY_RESEARCH_PROVIDER = env("FACTORY_RESEARCH_PROVIDER", default="")
FACTORY_RESEARCH_PROVIDER_TIER = env("FACTORY_RESEARCH_PROVIDER_TIER", default="")
SAEIT_BRIDGE_SECRET = env("SAEIT_BRIDGE_SECRET", default="")
if SAEIT_ENV == "staging" and any((
    PRODUCTION_PUBLICATION_ENABLED, REAL_PAYMENTS_ENABLED,
    TREASURY_EXECUTION_ENABLED, CRYPTO_EXECUTION_ENABLED,
)):
    raise RuntimeError("Production publication/payment/treasury/crypto execution must be disabled in staging")

FACTORY_ENVIRONMENT = SAEIT_ENV if SAEIT_ENV == "staging" else env("FACTORY_ENVIRONMENT", default="development")
STAGING_RESEARCH_API_KEY = env("STAGING_RESEARCH_API_KEY", default="")
