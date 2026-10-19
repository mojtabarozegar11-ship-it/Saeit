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

# Compiled Python wheels may live in CloudLinux's lib64. Never mix 3.10
# site-packages with a 3.11 Passenger interpreter (or vice versa).
# No executable .pth hooks are replayed.
py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
for root in (
    os.path.join(os.path.expanduser("~"), "virtualenv", "Saeit", py_version),
    os.path.join(os.path.expanduser("~"), "virtualenv", "repositories", "Saeit", py_version),
    sys.prefix,
):
    for dirname in ("lib", "lib64"):
        compiled = os.path.join(root, dirname, "python" + py_version, "site-packages")
        if os.path.isdir(compiled) and compiled not in sys.path:
            sys.path.insert(1, compiled)

from config.wsgi import application
