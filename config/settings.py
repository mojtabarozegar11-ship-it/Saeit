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
    # Historical MojPlayWin commerce schema; all public/payment gates remain fail-closed.
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

# Isolated English MOJ PROP runtime. The alias is inert unless staging opts in
# explicitly; the factory/default database is never replaced.
MPW_MOJPROP_IDENTITY_DIGEST_SECRET = env(
    "MPW_MOJPROP_IDENTITY_DIGEST_SECRET", default=""
)
MPW_MOJPROP_LOGIN_CHALLENGE_TTL_SECONDS = env.int(
    "MPW_MOJPROP_LOGIN_CHALLENGE_TTL_SECONDS", default=600
)
MPW_MOJPROP_LOGIN_MAX_ATTEMPTS = env.int(
    "MPW_MOJPROP_LOGIN_MAX_ATTEMPTS", default=5
)

# Paid-simulation learner portal: independent four-part hold. No customer
# emails, public account access or uploads until all owner release evidence
# (including shared throttling and recoverability) is verified.
MPW_MOJPROP_BUYER_PORTAL_APPROVED = env.bool(
    "MPW_MOJPROP_BUYER_PORTAL_APPROVED", default=False
)
MPW_MOJPROP_BUYER_TRANSACTIONAL_EMAIL_APPROVED = env.bool(
    "MPW_MOJPROP_BUYER_TRANSACTIONAL_EMAIL_APPROVED", default=False
)
MPW_MOJPROP_BUYER_SHARED_RATE_LIMIT_VERIFIED = env.bool(
    "MPW_MOJPROP_BUYER_SHARED_RATE_LIMIT_VERIFIED", default=False
)
MPW_MOJPROP_BUYER_DELIVERY_RECOVERY_VERIFIED = env.bool(
    "MPW_MOJPROP_BUYER_DELIVERY_RECOVERY_VERIFIED", default=False
)
MPW_MOJPROP_RECONCILIATION_SOURCE_ALIAS = env(
    "MPW_MOJPROP_RECONCILIATION_SOURCE_ALIAS", default=""
)
MPW_MOJPROP_DB_ALIAS_ENABLED = env.bool(
    "MPW_MOJPROP_DB_ALIAS_ENABLED", default=False
)
MPW_MOJPROP_DEPLOYMENT_ENV = env(
    "MPW_MOJPROP_DEPLOYMENT_ENV", default=""
)
MPW_MOJPROP_STAGING_IDENTITY_ROUTE_ENABLED = env.bool(
    "MPW_MOJPROP_STAGING_IDENTITY_ROUTE_ENABLED", default=False
)
MPW_MOJPROP_STAGING_ROUTE_TOKEN = env(
    "MPW_MOJPROP_STAGING_ROUTE_TOKEN", default=""
)
MPW_MOJPROP_STAGING_INTERNAL_IPS = tuple(
    env.list("MPW_MOJPROP_STAGING_INTERNAL_IPS", default=["127.0.0.1", "::1"])
)

# Dedicated live Starter30 release switches. All default closed; these are
# separate from the generic store gateway and never authorize the factory DB.
MPW_MOJPROP_PRODUCTION_RELEASE_APPROVED = env.bool(
    "MPW_MOJPROP_PRODUCTION_RELEASE_APPROVED", default=False
)
MPW_MOJPROP_TRX_RELEASE_ENABLED = env.bool(
    "MPW_MOJPROP_TRX_RELEASE_ENABLED", default=False
)
MPW_MOJPROP_TRX_RPC_ATTESTED = env.bool(
    "MPW_MOJPROP_TRX_RPC_ATTESTED", default=False
)
# A private offline-custody attested pool of public per-invoice TRON addresses.
# Fail closed by default. Never place owner wallet seeds or private keys here.
MPW_MOJPROP_INVOICE_ADDRESS_POOL_VERIFIED = env.bool(
    "MPW_MOJPROP_INVOICE_ADDRESS_POOL_VERIFIED", default=False
)
MPW_MOJPROP_INVOICE_ADDRESS_POOL_JSON = env(
    "MPW_MOJPROP_INVOICE_ADDRESS_POOL_JSON", default=""
)
MPW_MOJPROP_INVOICE_ADDRESS_CONTROL_REF = env(
    "MPW_MOJPROP_INVOICE_ADDRESS_CONTROL_REF", default=""
)
# Checkout email verification and cross-account anti-abuse require separate,
# owner-reviewed release controls. Neither switch sends email when false.
MPW_MOJPROP_PREINVOICE_TRANSACTIONAL_EMAIL_APPROVED = env.bool(
    "MPW_MOJPROP_PREINVOICE_TRANSACTIONAL_EMAIL_APPROVED", default=False
)
MPW_MOJPROP_RPC_A_SOURCE_ID = env("MPW_MOJPROP_RPC_A_SOURCE_ID", default="")
MPW_MOJPROP_RPC_A_OPERATOR_ID = env("MPW_MOJPROP_RPC_A_OPERATOR_ID", default="")
MPW_MOJPROP_RPC_A_ENDPOINT = env("MPW_MOJPROP_RPC_A_ENDPOINT", default="")
MPW_MOJPROP_RPC_A_API_KEY = env("MPW_MOJPROP_RPC_A_API_KEY", default="")
MPW_MOJPROP_RPC_B_SOURCE_ID = env("MPW_MOJPROP_RPC_B_SOURCE_ID", default="")
MPW_MOJPROP_RPC_B_OPERATOR_ID = env("MPW_MOJPROP_RPC_B_OPERATOR_ID", default="")
MPW_MOJPROP_RPC_B_ENDPOINT = env("MPW_MOJPROP_RPC_B_ENDPOINT", default="")
MPW_MOJPROP_RPC_B_API_KEY = env("MPW_MOJPROP_RPC_B_API_KEY", default="")
if MPW_MOJPROP_DB_ALIAS_ENABLED:
    if MPW_MOJPROP_DEPLOYMENT_ENV not in ("staging", "production"):
        raise RuntimeError("MOJ PROP database alias requires staging or production")
    if (
        MPW_MOJPROP_DEPLOYMENT_ENV == "production"
        and MPW_MOJPROP_PRODUCTION_RELEASE_APPROVED is not True
    ):
        raise RuntimeError("MOJ PROP production alias requires explicit release approval")
    _mojprop_database_url = env("MPW_MOJPROP_DATABASE_URL", default="")
    if not _mojprop_database_url:
        raise RuntimeError("MPW_MOJPROP_DATABASE_URL is required when enabled")
    if not MPW_MOJPROP_IDENTITY_DIGEST_SECRET:
        raise RuntimeError("MOJ PROP identity digest secret is required when enabled")
    if (
        not MPW_MOJPROP_RECONCILIATION_SOURCE_ALIAS
        or MPW_MOJPROP_RECONCILIATION_SOURCE_ALIAS == "mojprop"
    ):
        raise RuntimeError("MOJ PROP source alias must be explicit and distinct")
    DATABASES["mojprop"] = environ.Env.db_url_config(_mojprop_database_url)
    DATABASE_ROUTERS = ("config.mojprop_db_router.MojPropDatabaseRouter",)
else:
    DATABASE_ROUTERS = ()

if MPW_MOJPROP_STAGING_IDENTITY_ROUTE_ENABLED:
    if not MPW_MOJPROP_DB_ALIAS_ENABLED or MPW_MOJPROP_DEPLOYMENT_ENV != "staging":
        raise RuntimeError(
            "MOJ PROP staging identity route requires the staging database alias"
        )
    if len(MPW_MOJPROP_STAGING_ROUTE_TOKEN) < 32:
        raise RuntimeError(
            "MOJ PROP staging identity route token must be at least 32 characters"
        )

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

# Public receiving address verified against owner's native-TRX Trust Wallet QR.
# Source merge alone never permits a payable customer invoice. Independently
# approved native billing and finalized-chain verification are separate gates.
# No keys, mnemonic or secrets are stored here; do not infer www/other domains.
from services.mojtaba_tron_owner_receiver import (
    APPROVED_NATIVE_TRX_RECIPIENT as MPW_TRX_OWNER_RECEIVER,
    owner_merchant_registry,
)
MPW_TRX_INVOICE_RELEASE_VERIFIED = env.bool("MPW_TRX_INVOICE_RELEASE_VERIFIED", default=False)
MPW_TRX_SOLIDITY_RELEASE_VERIFIED = env.bool("MPW_TRX_SOLIDITY_RELEASE_VERIFIED", default=False)

# Historical, already-paid core-walletless digital entitlement bridge.
# SOURCE ONLY until independent DB/media restore + authenticated buyer/download
# adapter are reviewed. Never enable based solely on a paid flag or QR alone.
MPW_WALLETLESS_EXISTING_PAID_DIGITAL_ACCESS_ENABLED = env.bool(
    "MPW_WALLETLESS_EXISTING_PAID_DIGITAL_ACCESS_ENABLED", default=False
)

MPW_TRX_MERCHANT_BINDINGS = owner_merchant_registry(
    invoice_enabled=MPW_TRX_INVOICE_RELEASE_VERIFIED,
    finality_enabled=MPW_TRX_SOLIDITY_RELEASE_VERIFIED,
)


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
# Fail closed: only enable after SMTP ownership, consent, privacy and backup are checked.
MOJTABA_SIGNAL_FREE_SIGNUP_ENABLED = env.bool("MOJTABA_SIGNAL_FREE_SIGNUP_ENABLED", default=False)

# Cross-device guest recovery is source-only until the full checkout graph, schema lineage,
# SMTP ownership/consent and rollback are independently verified. Both flags stay off.
MPW_GUEST_RECOVERY_ENABLED = env.bool("MPW_GUEST_RECOVERY_ENABLED", default=False)
MPW_GUEST_RECOVERY_EMAIL_APPROVED = env.bool("MPW_GUEST_RECOVERY_EMAIL_APPROVED", default=False)
MPW_GUEST_EMAIL_SEND_APPROVED = env.bool("MPW_GUEST_EMAIL_SEND_APPROVED", default=False)

# Merchant runtime inputs. Defaults never authorize invoices, delivery or mail.
MPW_COMMERCE_RELEASE_READY = env.bool("MPW_COMMERCE_RELEASE_READY", default=False)
MPW_TRX_BACKGROUND_RECONCILE_ENABLED = env.bool("MPW_TRX_BACKGROUND_RECONCILE_ENABLED", default=False)
# Optional private TronGrid access credential; never expose in templates or logs.
MPW_TRONGRID_API_KEY = env("MPW_TRONGRID_API_KEY", default="")
MPW_COMMERCE_DOWNLOADS_ENABLED = env.bool("MPW_COMMERCE_DOWNLOADS_ENABLED", default=False)
MPW_WALLETLESS_TRX_PUBLIC_ENABLED = env.bool("MPW_WALLETLESS_TRX_PUBLIC_ENABLED", default=False)
MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED = env.bool("MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED", default=False)
MPW_WALLETLESS_TRX_PUBLIC_RELEASE_AUTHORIZED = env.bool("MPW_WALLETLESS_TRX_PUBLIC_RELEASE_AUTHORIZED", default=False)
MPW_COMMERCE_PRIVATE_ASSET_ROOT = env("MPW_COMMERCE_PRIVATE_ASSET_ROOT", default="")
MPW_TRX_PUBLIC_PRODUCT_IDS = tuple(dict.fromkeys(
    int(value) for value in env.list("MPW_TRX_PUBLIC_PRODUCT_IDS", default=[])
    if str(value).isascii() and str(value).isdigit() and int(value) > 0
))


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
