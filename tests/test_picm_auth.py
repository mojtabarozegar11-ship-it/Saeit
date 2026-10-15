import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from core.picm_auth import normalize_username


class PICMLoginTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.patch = patch.dict(os.environ, {"PICM_STORAGE_DIR": self.temp.name})
        self.patch.start()
        self.addCleanup(self.patch.stop)
        get_user_model().objects.create_user(username="09170000000", password="unit-test-secret", is_staff=False)

    def test_accepts_persian_and_arabic_digits(self):
        self.assertEqual(normalize_username("۰۹۱۷۰۰۰۰۰۰۰"), "09170000000")
        self.assertEqual(normalize_username("٠٩١٧٠٠٠٠٠٠٠"), "09170000000")

    def test_no_plaintext_secret_in_template(self):
        from django.conf import settings
        html = (settings.BASE_DIR / "templates/picm/login.html").read_text()
        self.assertIn('type="password"', html)
        self.assertIn("csrf_token", html)
        self.assertNotIn("unit-test-secret", html)

    def test_login_and_logout_sessions(self):
        # Explicit URL route is deployed independently in MojPlayWin production;
        # RequestFactory tests the view without modifying global company URLs.
        from django.test import RequestFactory
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.contrib.messages.middleware import MessageMiddleware
        from django.contrib.auth.middleware import AuthenticationMiddleware
        from core.picm_auth import picm_login, picm_logout
        from django.contrib.auth.models import AnonymousUser
        factory = RequestFactory()
        req = factory.post("/picm/login/", data={"username":"۰۹۱۷۰۰۰۰۰۰۰", "password":"unit-test-secret"})
        SessionMiddleware(lambda x:None).process_request(req)
        req.session.save()
        req.user = AnonymousUser()
        response=picm_login(req)
        self.assertEqual(response.status_code,302)
        self.assertEqual(response.url,"/picm/")
        self.assertIn("_auth_user_id",req.session)
        out=factory.post("/picm/logout/")
        out.session=req.session
        out.user=get_user_model().objects.get(username="09170000000")
        response=picm_logout(out)
        self.assertEqual(response.status_code,302)
        self.assertNotIn("_auth_user_id",out.session)

    def test_bad_password_is_generic_and_throttled(self):
        from django.test import RequestFactory
        from django.contrib.auth.models import AnonymousUser
        from core.picm_auth import picm_login
        factory=RequestFactory()
        for _ in range(6):
            req=factory.post("/picm/login/", data={"username":"09170000000","password":"bad"})
            req.user=AnonymousUser()
            response=picm_login(req)
            self.assertEqual(response.status_code,200)
        self.assertTrue((Path(self.temp.name)/".picm-login-attempts.json").is_file())
