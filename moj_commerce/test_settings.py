"""Isolated CI settings. Never use to configure the production website."""
import os
SECRET_KEY = 'isolated-test-only-not-for-live-' + ('k' * 32)
DEBUG = True
USE_TZ = True
TIME_ZONE = 'UTC'
ALLOWED_HOSTS = ['testserver', 'localhost']
ROOT_URLCONF = 'moj_commerce.urls'
INSTALLED_APPS = [
    'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions',
    'moj_commerce.apps.MojCommerceConfig',
]
MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
]
# These credentials belong only to short-lived GitHub Actions containers.
# No production DB URL is ever loaded or referenced in this test-only module.
if os.environ.get('MOJ_COMMERCE_TEST_MYSQL') == '1':
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'moj_commerce_ci',
        'USER': 'root',
        'PASSWORD': 'synthetic-test-only-2026',
        'HOST': '127.0.0.1',
        'PORT': '3306',
        'OPTIONS': {'charset': 'utf8mb4', 'init_command': "SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED"},
        'TEST': {'CHARSET': 'utf8mb4', 'COLLATION': 'utf8mb4_unicode_ci'},
    }}
elif os.environ.get('MOJ_COMMERCE_TEST_POSTGRES') == '1':
    DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'moj_commerce_ci',
                            'USER': 'postgres', 'PASSWORD': 'postgres', 'HOST': '127.0.0.1', 'PORT': '5432'}}
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates',
              'APP_DIRS': True, 'OPTIONS': {}}]
MOJ_COMMERCE_RECEIVER_ENABLED = False
MOJ_COMMERCE_FULFILL_SECRET = ''
MOJ_COMMERCE_FINALIZED_TRON_CHECKER = None
MOJ_COMMERCE_PRIVATE_ROOT = ''

# Synthetic legacy tests may use manual fake addresses; prod default is True.
MOJ_COMMERCE_REQUIRE_SIGNED_WALLET = False
MOJ_COMMERCE_TRONGRID_API_KEY = ''

# All operational switches OFF in source/test settings unless explicitly overridden.
MOJ_COMMERCE_CHECKOUT_ENABLED = False
MOJ_COMMERCE_SCANNER_ENABLED = False
MOJ_COMMERCE_REQUIRE_FILE_PRESENT = True
MOJ_COMMERCE_TRX_RATE_PROVIDER = None
# Monitoring is read-only, no schedule, no worker and no live processing.
MOJ_COMMERCE_MONITOR_STALE_SECONDS = 300
# No automatic operational mutation; opt-in recovery command must pass --apply.
MOJ_COMMERCE_RECOVERY_ENABLED = False

# Source-only: no approved independent second provider exists in test settings.
MOJ_COMMERCE_TRON_QUORUM_SOURCES = None

# No invoice self-healing without explicit production operator opt-in.
MOJ_COMMERCE_SELF_REPAIR_ENABLED = False
