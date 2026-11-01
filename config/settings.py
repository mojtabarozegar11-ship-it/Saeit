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
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "rest_framework",
    "core",
    "farnaz.apps.FarnazConfig",
    "command_center",
    "enterprise_portal.apps.EnterprisePortalConfig",
    "ecosystem_hub.apps.EcosystemHubConfig",
    "company_messaging.apps.CompanyMessagingConfig",
    "company_marketing.apps.CompanyMarketingConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "enterprise_portal.security.PrivateOfficeAdminMfaMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.RequestAuditMiddleware",
]

# Fail closed for all non-test private company sessions.
# Do not expose a production environment toggle that can disable office MFA.
COMPANY_OFFICE_REQUIRE_MFA = True
# PHP V7 remains the financial source of truth until a separately approved cutover.
# The aggregate bridge is disabled unless its private SQLite source is explicit.
ZM_PHP_LEDGER_READONLY_PATH = env("ZM_PHP_LEDGER_READONLY_PATH", default="")

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

# No automated enterprise analysis until independently authorized.
ECOSYSTEM_SCHEDULED_ANALYSIS_ENABLED = env.bool("ECOSYSTEM_SCHEDULED_ANALYSIS_ENABLED", default=False)

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

# Zomorod company communication: disabled until SMTP/provider contracts,
# opt-in evidence, HTTPS security and the private worker release gate pass.
COMPANY_MESSAGING_SEND_ENABLED = env.bool("COMPANY_MESSAGING_SEND_ENABLED", default=False)
COMPANY_SMS_KAVENEGAR_KEY = env("COMPANY_SMS_KAVENEGAR_KEY", default="")
COMPANY_SMS_KAVENEGAR_SENDER = env("COMPANY_SMS_KAVENEGAR_SENDER", default="")
COMPANY_TELEGRAM_BOT_TOKEN = env("COMPANY_TELEGRAM_BOT_TOKEN", default="")
COMPANY_WHATSAPP_ACCESS_TOKEN = env("COMPANY_WHATSAPP_ACCESS_TOKEN", default="")
COMPANY_WHATSAPP_PHONE_ID = env("COMPANY_WHATSAPP_PHONE_ID", default="")
COMPANY_WHATSAPP_TEMPLATE_NAME = env("COMPANY_WHATSAPP_TEMPLATE_NAME", default="")
COMPANY_WHATSAPP_TEMPLATE_LANGUAGE = env("COMPANY_WHATSAPP_TEMPLATE_LANGUAGE", default="fa")
COMPANY_MESSAGING_EMAIL_ENABLED = env.bool("COMPANY_MESSAGING_EMAIL_ENABLED", default=False)
COMPANY_MESSAGING_SMS_ENABLED = env.bool("COMPANY_MESSAGING_SMS_ENABLED", default=False)
COMPANY_MESSAGING_TELEGRAM_ENABLED = env.bool("COMPANY_MESSAGING_TELEGRAM_ENABLED", default=False)
COMPANY_MESSAGING_WHATSAPP_ENABLED = env.bool("COMPANY_MESSAGING_WHATSAPP_ENABLED", default=False)

# Domestic official bot connections. Off unless each account has been paired and verified.
COMPANY_MESSAGING_BALE_ENABLED = env.bool("COMPANY_MESSAGING_BALE_ENABLED", default=False)
COMPANY_MESSAGING_EITAA_ENABLED = env.bool("COMPANY_MESSAGING_EITAA_ENABLED", default=False)
COMPANY_MESSAGING_RUBIKA_ENABLED = env.bool("COMPANY_MESSAGING_RUBIKA_ENABLED", default=False)
COMPANY_BALE_BOT_TOKEN = env("COMPANY_BALE_BOT_TOKEN", default="")
COMPANY_EITAA_APP_TOKEN = env("COMPANY_EITAA_APP_TOKEN", default="")
COMPANY_RUBIKA_BOT_TOKEN = env("COMPANY_RUBIKA_BOT_TOKEN", default="")
COMPANY_MARKETING_PUBLISH_ENABLED = env.bool("COMPANY_MARKETING_PUBLISH_ENABLED", default=False)
