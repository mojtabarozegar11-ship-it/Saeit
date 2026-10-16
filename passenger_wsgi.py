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

# CloudLinux's managed lswsgi must remain the running Passenger process.
# The app's Python 3.10 virtualenv uses both lib/ and lib64/ site directories,
# verified to restore the compiled pydantic_core wheel and Django WSGI import.
import site

VENV_ROOT = os.path.join(os.path.expanduser("~"), "virtualenv", "Saeit", "3.10")
for package_dir in (
    os.path.join(VENV_ROOT, "lib64", "python3.10", "site-packages"),
    os.path.join(VENV_ROOT, "lib", "python3.10", "site-packages"),
):
    if not os.path.isdir(package_dir):
        raise RuntimeError("CloudLinux virtualenv site-packages directory is unavailable")
    site.addsitedir(package_dir)

from config.wsgi import application
