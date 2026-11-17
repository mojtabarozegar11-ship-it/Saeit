"""Minimal, isolated non-production Django settings for world20 HTTP tests."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "ci-world20-local-unprivileged-test-only"
DEBUG = False
ALLOWED_HOSTS = ["mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir", "testserver"]
INSTALLED_APPS = []
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware"]
ROOT_URLCONF = "config.world20_ci_urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "core" / "templates"],
    "APP_DIRS": False,
    "OPTIONS": {"context_processors": []},
}]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
STATIC_URL = "/static/"
