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

# Temporary narrow diagnostic: capture the first and any nested Django setup callers.
import threading
import traceback
from django.apps import apps as django_apps
from django.apps.registry import Apps

print("PASSENGER_SETUP_INITIAL_LOADING=" + str(django_apps.loading), file=sys.stderr)
print("PASSENGER_SETUP_INITIAL_READY=" + str(django_apps.ready), file=sys.stderr)
_original_populate = Apps.populate
_populate_calls = 0

def _trace_setup_caller(self, installed_apps):
    global _populate_calls
    _populate_calls += 1
    if _populate_calls <= 4:
        print("PASSENGER_SETUP_CALL=%s loading=%s ready=%s thread=%s" % (
            _populate_calls, self.loading, self.ready, threading.current_thread().name
        ), file=sys.stderr)
        if self.loading:
            print("PASSENGER_REENTRANT_CALL_STACK_BEGIN", file=sys.stderr)
            traceback.print_stack(limit=35, file=sys.stderr)
            print("PASSENGER_REENTRANT_CALL_STACK_END", file=sys.stderr)
    return _original_populate(self, installed_apps)

Apps.populate = _trace_setup_caller

# CloudLinux's Passenger interpreter already activates this app's virtualenv.
# Avoid site.addsitedir(): it re-runs executable .pth hooks and can re-enter
# Django initialization before Passenger imports this WSGI application.
from config.wsgi import application
