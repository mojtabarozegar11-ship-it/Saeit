"""CI-only settings for validating draft ETH/TRX Django models and migrations."""
SECRET_KEY = "local-test-only-not-production"
DEBUG = False
ALLOWED_HOSTS = ["mojplaywin.com", "testserver", "localhost", "zomorodmelal.ir"]
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.contenttypes",
    "core",
    "mpw_native_checkout",
    "mpw_commerce",
]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]
SESSION_ENGINE = "django.contrib.sessions.backends.db"
LOGIN_URL = "/login/"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
}]
ROOT_URLCONF = "tests.native_checkout_urls"
SILENCED_SYSTEM_CHECKS = []
