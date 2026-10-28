"""Dedicated WSGI entry point for a future isolated cPanel Python app.

Must be mounted under /banknew-api/ only after separate secure provision.
Never replace the shared site's passenger_wsgi.py or Django URLConf.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ["DJANGO_SETTINGS_MODULE"] = "banknew.isolated_settings"
application = get_wsgi_application()
