"""CloudLinux Python Selector startup file in the dedicated office app root.

Never use this module as the public site\u0027s WSGI entrypoint.
"""
import os
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))
os.environ["DJANGO_SETTINGS_MODULE"] = "office_runtime.settings"

from office_runtime.passenger_wsgi import application  # noqa: E402,F401
