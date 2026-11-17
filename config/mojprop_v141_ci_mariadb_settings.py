"""Django settings exclusively for an ephemeral GitHub Actions MariaDB service.

Never use against company/factory/cPanel/production hosts. The GitHub job
creates/destroys its own disposable test database. These settings intentionally
refuse to run outside a self-contained GitHub Actions runner on loopback.
"""
import os

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise RuntimeError("MOJ PROP ephemeral MariaDB settings require GitHub Actions")
if os.environ.get("MOJPROP_V141_EPHEMERAL_DB") != "test-container-only":
    raise RuntimeError("explicit ephemeral test-container intent required")
if os.environ.get("MOJPROP_MARIADB_HOST") != "127.0.0.1":
    raise RuntimeError("database host must be the runner loopback")
if os.environ.get("MOJPROP_MARIADB_DATABASE") != "mojprop_v141_ci_only":
    raise RuntimeError("database name must be the disposable CI schema")
if not os.environ.get("MOJPROP_MARIADB_PASSWORD"):
    raise RuntimeError("local CI-only database credentials required")

SECRET_KEY = "github-actions-ephemeral-unit-only-no-production"
DEBUG = False
ALLOWED_HOSTS = ["testserver"]
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "prop_firm.apps.MojPropConfig",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "mojprop_v141_ci_only",
        "USER": "root",
        "PASSWORD": os.environ["MOJPROP_MARIADB_PASSWORD"],
        "HOST": "127.0.0.1",
        "PORT": "3306",
        "OPTIONS": {"init_command": "SET sql_mode='STRICT_TRANS_TABLES'"},
        "TEST": {"NAME": "test_mojprop_v141_ci_only"},
    }
}
# Template rendering is restricted to the repository template directory.
# No live web server or public user session is started by these CI settings.
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_URL = "/static/"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": []},
}]
LOGIN_URL = "/admin/login/"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
MIDDLEWARE = []
ROOT_URLCONF = None
