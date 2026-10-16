import os
import sys
import traceback

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.apps.registry import Apps
from django.core.wsgi import get_wsgi_application

_original_populate = Apps.populate

def _trace_reentrant_populate(self, installed_apps):
    if self.loading:
        print("PASSENGER_REENTRANT_CALL_STACK_BEGIN", file=sys.stderr, flush=True)
        traceback.print_stack(file=sys.stderr)
        print("PASSENGER_REENTRANT_CALL_STACK_END", file=sys.stderr, flush=True)
    return _original_populate(self, installed_apps)

Apps.populate = _trace_reentrant_populate
application = get_wsgi_application()
