"""Dedicated WSGI entrypoint; never reuse the shared Django application."""
import os
from django.core.exceptions import ImproperlyConfigured

if os.environ.get("DJANGO_SETTINGS_MODULE") not in (None,"config.mojprop_settings"):
    raise ImproperlyConfigured("MOJ PROP requires its own process and settings")
os.environ["DJANGO_SETTINGS_MODULE"]="config.mojprop_settings"
from django.core.wsgi import get_wsgi_application
application=get_wsgi_application()
