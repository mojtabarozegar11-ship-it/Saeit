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

# Temporary startup probe: record who re-enters Django setup in Passenger's own process.
import traceback
from django.apps.registry import Apps

_original_apps_populate = Apps.populate
def _trace_passenger_reentrant_setup(self, installed_apps):
    if self.loading:
        print("PASSENGER_REENTRANT_CALL_STACK_BEGIN", file=sys.stderr)
        traceback.print_stack(file=sys.stderr)
        print("PASSENGER_REENTRANT_CALL_STACK_END", file=sys.stderr)
    return _original_apps_populate(self, installed_apps)

Apps.populate = _trace_passenger_reentrant_setup

from config.wsgi import application
