"""Passenger entry point for separate app, never the existing Saaeit root."""
import os
os.environ["DJANGO_SETTINGS_MODULE"]="mojprop_isolated.settings"
from django.core.wsgi import get_wsgi_application
application=get_wsgi_application()
