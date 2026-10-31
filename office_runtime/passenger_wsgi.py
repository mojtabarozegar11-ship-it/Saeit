"""WSGI entrypoint for the independently registered cPanel Python app."""
import os
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))
os.environ["DJANGO_SETTINGS_MODULE"] = "office_runtime.settings"

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
