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
    # Required for CommerceInvoice/CommerceFulfillment entitlement checks.
    "mpw_commerce.apps.MpwCommerceConfig",
    "farnaz.apps.FarnazConfig",
    "command_center",
    # Accounting ledger is part of the production management desk.
    "accounting.apps.AccountingConfig",
    "prop_firm.apps.MojPropConfig",
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

# The isolated database and router are opt-in and staging-only. Defaults remain
# completely inert so the factory database cannot be affected by configuration
# drift or an incomplete deployment.
MPW_MOJPROP_DB_ALIAS_ENABLED = env.bool(
    "MPW_MOJPROP_DB_ALIAS_ENABLED", default=False
)
MPW_MOJPROP_DEPLOYMENT_ENV = env(
    "MPW_MOJPROP_DEPLOYMENT_ENV", default=""
)
if MPW_MOJPROP_DB_ALIAS_ENABLED:
    if MPW_MOJPROP_DEPLOYMENT_ENV != "staging":
        raise RuntimeError(
            "MOJ PROP database alias can only be enabled in staging"
        )
    _mojprop_database_url = env("MPW_MOJPROP_DATABASE_URL", default="")
    _mojprop_identity_secret = env(
        "MPW_MOJPROP_IDENTITY_DIGEST_SECRET", default=""
    )
    _mojprop_source_alias = env(
        "MPW_MOJPROP_RECONCILIATION_SOURCE_ALIAS", default=""
    )
    if not _mojprop_database_url:
        raise RuntimeError(
            "MPW_MOJPROP_DATABASE_URL is required when the alias is enabled"
        )
    if not _mojprop_identity_secret:
        raise RuntimeError(
            "MPW_MOJPROP_IDENTITY_DIGEST_SECRET is required when the alias is enabled"
        )
    if not _mojprop_source_alias or _mojprop_source_alias == "mojprop":
        raise RuntimeError(
            "MOJ PROP reconciliation source must be explicit and distinct"
        )
    DATABASES["mojprop"] = environ.Env.db_url_config(_mojprop_database_url)
    DATABASE_ROUTERS = (
        "config.mojprop_db_router.MojPropDatabaseRouter",
    )
else:
    DATABASE_ROUTERS = ()

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

# Guest purchase recovery remains fail-closed until SMTP ownership, privacy,
# rollback and owner approval are independently verified.
MPW_GUEST_RECOVERY_ENABLED = env.bool("MPW_GUEST_RECOVERY_ENABLED", default=False)
MPW_GUEST_RECOVERY_EMAIL_APPROVED = env.bool("MPW_GUEST_RECOVERY_EMAIL_APPROVED", default=False)
MPW_GUEST_EMAIL_SEND_APPROVED = env.bool("MPW_GUEST_EMAIL_SEND_APPROVED", default=False)

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



# MOJ-PROP-01 effective-app gates. All remain disabled until independently
# evidenced capital, jurisdiction, broker, KYC, settlement and owner-canary gates.
MPW_MOJPROP_PLAN1_ROUTE_ENABLED = env.bool(
    "MPW_MOJPROP_PLAN1_ROUTE_ENABLED", default=False
)
MPW_MOJPROP_PLAN1_LIVE_INVOICE_ENABLED = env.bool(
    "MPW_MOJPROP_PLAN1_LIVE_INVOICE_ENABLED", default=False
)
MPW_MOJPROP_PLAN1_RECIPIENT = env(
    "MPW_MOJPROP_PLAN1_RECIPIENT", default=""
)
MPW_MOJPROP_PLAN1_TRUSTED_CONTRACT_SHA256 = env(
    "MPW_MOJPROP_PLAN1_TRUSTED_CONTRACT_SHA256", default=""
)
for _mojprop_gate in (
    "INDEPENDENT_CAPITAL_PROOF",
    "JURISDICTION_APPROVAL",
    "BROKER_CONTRACT",
    "MERCHANT_SETTLEMENT_READY",
    "KYC_ELIGIBILITY_READY",
    "OWNER_CANARY_COMPLETE",
):
    globals()["MPW_MOJPROP_PLAN1_" + _mojprop_gate] = env.bool(
        "MPW_MOJPROP_PLAN1_" + _mojprop_gate, default=False
    )
# MPW_TRX_PUBLIC_PRODUCT_ALLOWLIST_20261119
# Rights-cleared, active products already exposed by the MojPlayWin store.
MPW_TRX_PUBLIC_PRODUCT_IDS = (72, 225, 879)
MPW_COMMERCE_PRIVATE_ASSET_ROOT = "/home/zomorod2/MojPlayWin_Private_Assets"

# MPW_TRX_PUBLIC_RELEASE_ENABLE_20261119
# Owner-authorized public TRX storefront; payment proof remains server-verified.
MPW_COMMERCE_DOWNLOADS_ENABLED = True
MPW_WALLETLESS_TRX_PUBLIC_ENABLED = True
MPW_WALLETLESS_TRX_PUBLIC_RELEASE_AUTHORIZED = True
MPW_COMMERCE_RELEASE_READY = True
MPW_COMMERCE_INVOICING_ENABLED = True
MPW_COMMERCE_SETTLEMENT_ENABLED = True
MPW_COMMERCE_REAL_RPC_ENABLED = True
MPW_COMMERCE_AUTORECONCILE_ENABLED = True
MPW_COMMERCE_BUYER_SIGNATURE_ENABLED = True
MPW_COMMERCE_CUSTOMER_HTTP_ENABLED = True

# Isolated MOJ PROP identity/login adapter remains closed unless staging
# supplies a dedicated secret. These values do not enable routing, commerce,
# email delivery, or the English route.
MPW_MOJPROP_IDENTITY_DIGEST_SECRET = env(
    "MPW_MOJPROP_IDENTITY_DIGEST_SECRET", default=""
)
MPW_MOJPROP_LOGIN_CHALLENGE_TTL_SECONDS = env.int(
    "MPW_MOJPROP_LOGIN_CHALLENGE_TTL_SECONDS", default=600
)
MPW_MOJPROP_LOGIN_MAX_ATTEMPTS = env.int(
    "MPW_MOJPROP_LOGIN_MAX_ATTEMPTS", default=5
)

# Payment reconciliation remains closed until a private worker explicitly
# supplies the verified source database alias. This does not enable checkout.
MPW_MOJPROP_RECONCILIATION_SOURCE_ALIAS = env(
    "MPW_MOJPROP_RECONCILIATION_SOURCE_ALIAS", default=""
)
