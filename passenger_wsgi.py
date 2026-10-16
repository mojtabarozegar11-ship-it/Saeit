import os
import sys
import traceback

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.apps.registry import Apps
from django.core.wsgi import get_wsgi_application

_original_populate = Apps.populate


def _trace_reentrant_population(self, *args, **kwargs):
    if self.loading:
        print("RuntimeError: ZOMOROD_DJANGO_POPULATE_REENTERED", file=sys.stderr)
        traceback.print_stack(limit=48, file=sys.stderr)
    return _original_populate(self, *args, **kwargs)


Apps.populate = _trace_reentrant_population
application = get_wsgi_application()
