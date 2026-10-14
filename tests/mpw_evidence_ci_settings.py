"""Isolated SQLite test settings: no host or external integrations."""
SECRET_KEY = "evidence-ci-only-not-production"
DEBUG = False
ALLOWED_HOSTS = ["testserver", "mojplaywin.com", "localhost"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "rest_framework", "core", "command_center",
]
DATABASES = {"default": {"ENGINE":"django.db.backends.sqlite3", "NAME":":memory:"}}
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
SESSION_ENGINE = "django.contrib.sessions.backends.db"
ROOT_URLCONF = "tests.mpw_evidence_urls"
LOGIN_URL = "/admin/login/"
TEMPLATES = [{"BACKEND":"django.template.backends.django.DjangoTemplates",
    "APP_DIRS":True,"OPTIONS":{"context_processors":[
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages"]}}]
STATIC_URL = "/static/"
