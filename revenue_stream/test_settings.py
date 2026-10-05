"""Isolated tests only. Never point Passenger at this module."""
import tempfile
from pathlib import Path
BASE_DIR=Path(tempfile.mkdtemp(prefix='costkit-test-'))
SECRET_KEY='test-only-key-not-for-deployment-000000000000000000000'
DEBUG=False
ALLOWED_HOSTS=['testserver','localhost','127.0.0.1','zomorodmelal.ir']
INSTALLED_APPS=['django.contrib.contenttypes','django.contrib.sessions']
MIDDLEWARE=['django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware']
DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}}
SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies'
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
ROOT_URLCONF='revenue_stream.test_urls'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[Path(__file__).parent/'templates'],'APP_DIRS':False,'OPTIONS':{'context_processors':['django.template.context_processors.request']}}]
USE_TZ=True
