import os
from pathlib import Path

# Passenger starts from the application root on cPanel. Django settings then
# load the local .env. No secret is embedded in this file.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.chdir(Path(__file__).resolve().parent)

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
