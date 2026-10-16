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

# Use the two package locations proven by the read-only CloudLinux WSGI smoke test.
# Keep the cPanel-managed lswsgi process; do not re-exec a Passenger worker.
import site

VENV_ROOT = os.path.join(os.path.expanduser("~"), "virtualenv", "Saeit", "3.10")
for package_dir in (
    os.path.join(VENV_ROOT, "lib64", "python3.10", "site-packages"),
    os.path.join(VENV_ROOT, "lib", "python3.10", "site-packages"),
):
    if not os.path.isdir(package_dir):
        raise RuntimeError("CloudLinux virtualenv site-packages directory is unavailable")
    site.addsitedir(package_dir)

# Temporary Passenger reentrancy diagnostic.
import threading
import traceback
from django.apps import apps as django_apps
from django.apps.registry import Apps

print("PASSENGER_REGISTRY_INITIAL_LOADING=" + str(django_apps.loading), file=sys.stderr)
print("PASSENGER_REGISTRY_INITIAL_READY=" + str(django_apps.ready), file=sys.stderr)
print("PASSENGER_PRELOADED_CONFIG_WSGI=" + str("config.wsgi" in sys.modules), file=sys.stderr)

_original_populate = Apps.populate

def _trace_passenger_populate(self, installed_apps):
    print("PASSENGER_REENTRANT_CALL_STACK_BEGIN", file=sys.stderr)
    print("PASSENGER_POPULATE_STATE=loading:%s ready:%s apps_ready:%s thread:%s" % (
        self.loading, self.ready, self.apps_ready, threading.current_thread().name
    ), file=sys.stderr)
    if self.loading:
        print("PASSENGER_PROCESS_ID=" + str(os.getpid()), file=sys.stderr)
        frames = sys._current_frames()
        threads = {thread.ident: thread.name for thread in threading.enumerate()}
        for thread_id, frame in frames.items():
            print("PASSENGER_THREAD_FRAME=" + str(thread_id) + ":" + threads.get(thread_id, "unknown"), file=sys.stderr)
            traceback.print_stack(frame, limit=60, file=sys.stderr)
    try:
        result = _original_populate(self, installed_apps)
    except BaseException as error:
        print("PASSENGER_POPULATE_EXCEPTION=" + type(error).__name__, file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise
    else:
        print("PASSENGER_POPULATE_RESULT=success", file=sys.stderr)
        return result
    finally:
        print("PASSENGER_REENTRANT_CALL_STACK_END", file=sys.stderr)

Apps.populate = _trace_passenger_populate

from config.wsgi import application
