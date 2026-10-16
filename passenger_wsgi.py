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

# cPanel Passenger may launch this script with its system interpreter.
# Re-exec once with this application's CloudLinux virtualenv before importing Django.
INTERP = os.path.join(os.path.expanduser("~"), "virtualenv", "Saeit", "3.10", "bin", "python")
if not os.path.isfile(INTERP) or not os.access(INTERP, os.X_OK):
    raise RuntimeError("Configured Django virtualenv interpreter is unavailable")
if os.path.abspath(sys.executable) != os.path.abspath(INTERP):
    if os.environ.get("ZOMOROD_PASSENGER_REEXEC") == "1":
        raise RuntimeError("Passenger re-exec did not select the configured virtualenv")
    os.environ["ZOMOROD_PASSENGER_REEXEC"] = "1"
    os.execl(INTERP, INTERP, *sys.argv)

from config.wsgi import application
