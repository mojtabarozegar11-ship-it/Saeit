import os
import sys
import traceback

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.apps.registry import Apps
from django.core.wsgi import get_wsgi_application

_original_populate = Apps.populate


def _trace_reentrant_population(self, *args, **kwargs):
    if self.loading:
        print(
            "RuntimeError: ZOMOROD_DJANGO_POPULATE_REENTERED "
            f"ready={self.ready} apps_ready={self.apps_ready} models_ready={self.models_ready}",
            file=sys.stderr,
        )
        traceback.print_stack(limit=48, file=sys.stderr)
    try:
        return _original_populate(self, *args, **kwargs)
    except BaseException:
        print("ZOMOROD_DJANGO_POPULATE_FAILURE", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise


Apps.populate = _trace_reentrant_population
application = get_wsgi_application()
