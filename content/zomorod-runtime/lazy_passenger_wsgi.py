import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Load only this production app's environment before Django initializes.
env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    with open(env_path, encoding="utf-8", errors="replace") as env_file:
        for raw in env_file:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            if key:
                os.environ.setdefault(key, value)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# CloudLinux's Passenger interpreter activates the app's lib site-packages,
# while compiled wheels such as pydantic_core may be installed under lib64.
# Add the existing package directory directly; do not re-run executable .pth hooks.
venv_lib64 = os.path.join(
    os.path.expanduser("~"),
    "virtualenv",
    "Saeit",
    "3.10",
    "lib64",
    "python3.10",
    "site-packages",
)
if os.path.isdir(venv_lib64) and venv_lib64 not in sys.path:
    sys.path.insert(1, venv_lib64)

# Avoid site.addsitedir(): it re-runs executable .pth hooks and can re-enter
# Django initialization before Passenger imports this WSGI application.
# Passenger should import this module without recursively calling django.setup().
# The real WSGI object is constructed on the first request, after Passenger
# finishes module initialization. No edits to databases, models or URLs.
_app_instance = None

def application(environ, start_response):
    global _app_instance
    if _app_instance is None:
        from django.core.wsgi import get_wsgi_application
        _app_instance = get_wsgi_application()
    return _app_instance(environ, start_response)

