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
                if key.startswith("MPW_MOJPROP_"):
                    # MojProp release flags must follow this deployed .env,
                    # not a stale Passenger parent environment.
                    os.environ[key] = value
                else:
                    os.environ.setdefault(key, value)

# Keep the public host policy consistent across the WSGI bootstrap and Django.
# This only affects host/CSRF admission; it does not enable payments, invoices,
# trading, deployment, or any other commercial gate.
_PUBLIC_HOSTS = (
    "mojplaywin.com",
    "www.mojplaywin.com",
    "mojtaba.bot.ai",
    "www.mojtaba.bot.ai",
)
_PUBLIC_ORIGINS = tuple(f"https://{host}" for host in _PUBLIC_HOSTS)

def _append_csv_env(name, values):
    current = [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]
    for value in values:
        if value not in current:
            current.append(value)
    if current:
        os.environ[name] = ",".join(current)

_append_csv_env("ALLOWED_HOSTS", _PUBLIC_HOSTS)
_append_csv_env("DJANGO_ALLOWED_HOSTS", _PUBLIC_HOSTS)
_append_csv_env("CSRF_TRUSTED_ORIGINS", _PUBLIC_ORIGINS)
_append_csv_env("DJANGO_CSRF_TRUSTED_ORIGINS", _PUBLIC_ORIGINS)

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"

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
