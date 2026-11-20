"""Isolated process regression, never connect to a live database."""
import os
import subprocess
import sys
from pathlib import Path
from unittest import TestCase
ROOT=Path(__file__).resolve().parents[1]
FIXTURE={
 "DJANGO_SETTINGS_MODULE":"config.mojprop_settings",
 "MOJ_PROP_SECRET_KEY":"ci-only-"+("a"*64),
 "MOJ_PROP_DB_NAME":"zomorod2_mojprop",
 "MOJ_PROP_DB_USER":"zomorod2_mojprop_ci",
 "MOJ_PROP_DB_PASSWORD":"fixture-not-live"}
class DedicatedRuntimeTests(TestCase):
    def run_child(self,code,**overrides):
        env=dict(os.environ)
        env.update(FIXTURE)
        env.update(overrides)
        return subprocess.run([sys.executable,"-B","-c",code],cwd=ROOT,env=env,capture_output=True,text=True,timeout=45)
    def test_only_independent_database_and_app_registry(self):
        result=self.run_child("""
import django
django.setup()
from django.conf import settings
from django.apps import apps
from django.db import connections
assert list(settings.DATABASES)==["default"]
assert connections["default"].settings_dict["NAME"]=="zomorod2_mojprop"
assert not apps.is_installed("core")
assert apps.is_installed("prop_firm")
assert settings.DATABASE_ROUTERS==[]
assert settings.SESSION_COOKIE_NAME=="mojprop_session_v1"
assert settings.SESSION_COOKIE_PATH=="/moj-prop/"
assert not settings.MPW_SIMULATION_CHECKOUT_ENABLED
assert not settings.MPW_SIMULATION_TRADING_ENABLED
assert not settings.MPW_SIMULATION_IDENTITY_ENABLED
assert connections["default"].connection is None
""")
        self.assertEqual(result.returncode,0,result.stderr[-2000:])
    def test_shared_database_and_shared_principal_rejected(self):
        for change in ({"MOJ_PROP_DB_NAME":"zomorod2_sites_main"},{"MOJ_PROP_DB_USER":"zomorod2_sites_admin"},{"MOJ_PROP_DB_PASSWORD":""},{"MOJ_PROP_SECRET_KEY":"short"}):
            result=self.run_child("import config.mojprop_settings",**change)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("ImproperlyConfigured",result.stderr)
    def test_mounted_routes_and_landing_without_database_connection(self):
        result=self.run_child("""
import django
django.setup()
from django.urls import resolve, reverse, set_script_prefix, Resolver404
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.db import connections
set_script_prefix("/moj-prop/")
assert reverse("moj_prop_simulation_checkout")=="/moj-prop/checkout/start/"
assert resolve("/account/login/").url_name=="moj_prop_simulation_login"
for route in ("/store/","/admin/","/fa/","/commerce/moj-prop/plan1/start/"):
    try: resolve(route)
    except Resolver404: pass
    else: raise AssertionError("Unrelated route exposed")
request=RequestFactory().get("/",secure=True,HTTP_HOST="mojplaywin.com")
request.user=AnonymousUser()
response=resolve("/").func(request)
assert response.status_code==200
assert b"Do not send any funds" in response.content
assert b"Create 30 TRX invoice" not in response.content
assert b"/moj-prop/static/site/moj_prop.css" in response.content
assert connections["default"].connection is None
""")
        self.assertEqual(result.returncode,0,result.stderr[-2000:])
    def test_wsgi_rejects_existing_shared_settings(self):
        result=self.run_child("import config.mojprop_wsgi",DJANGO_SETTINGS_MODULE="config.settings")
        self.assertNotEqual(result.returncode,0)
        self.assertIn("requires its own process",result.stderr)
