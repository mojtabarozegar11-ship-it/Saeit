"""CI-only settings for validating draft ETH/TRX Django models and migrations."""
SECRET_KEY = "local-test-only-not-production"
DEBUG = False
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "core",
    "mpw_native_checkout",
]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
MIDDLEWARE = []
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
}]
ROOT_URLCONF = "tests.native_checkout_urls"
SILENCED_SYSTEM_CHECKS = []
