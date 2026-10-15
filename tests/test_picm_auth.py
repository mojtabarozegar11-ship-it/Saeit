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
        u = get_user_model().objects.create_user(username="picm-09170000000", password="unit-test-secret", is_staff=False)
        (Path(self.temp.name) / ".owner-user-id").write_text(str(u.pk)+"\n", encoding="ascii")

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
        self.assertEqual(response.url,"/picm/workspace/")
        self.assertIn("_auth_user_id",req.session)
        out=factory.post("/picm/logout/")
        out.session=req.session
        out.user=get_user_model().objects.get(username="picm-09170000000")
        response=picm_logout(out)
        self.assertEqual(response.status_code,302)
        self.assertNotIn("_auth_user_id",out.session)

    def test_two_pages_and_anonymous_workbench_protection(self):
        from django.test import RequestFactory
        from django.contrib.auth.models import AnonymousUser
        from core.picm_views import picm_page, picm_workbench
        factory = RequestFactory()
        anonymous = AnonymousUser()
        entry = factory.get("/picm/")
        entry.user = anonymous
        first = picm_page(entry)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(first.url, "/picm/login/")
        req = factory.get("/picm/workspace/")
        req.user = anonymous
        denied = picm_workbench(req)
        self.assertEqual(denied.status_code, 302)
        self.assertEqual(denied.url, "/picm/login/")
        user = get_user_model().objects.get(username="picm-09170000000")
        entry.user = user
        self.assertEqual(picm_page(entry).url, "/picm/workspace/")
        req.user = user
        workspace = picm_workbench(req)
        self.assertEqual(workspace.status_code, 200)
        self.assertIn(b'id="renderform"', workspace.content)
        self.assertIn(b'/picm/logout/', workspace.content)
        self.assertNotIn(b'href="/picm/login/"', workspace.content)
        login_req = factory.get("/picm/login/")
        login_req.user = user
        from core.picm_auth import picm_login
        self.assertEqual(picm_login(login_req).url, "/picm/workspace/")

    def test_nonowner_admin_and_other_authenticated_accounts_denied(self):
        from django.test import RequestFactory
        from django.contrib.auth.models import AnonymousUser
        from core.picm_auth import picm_login, picm_logout
        from core.picm_views import picm_page, picm_workbench
        from core.picm_access import owner_allowed
        admin = get_user_model().objects.create_superuser(
            username="unrelated-site-admin", password="unit-test-admin",
            email="nobody@example.org")
        rf = RequestFactory()
        self.assertFalse(owner_allowed(admin))
        req = rf.get("/picm/")
        req.user = admin
        self.assertEqual(picm_page(req).status_code, 403)
        req = rf.get("/picm/workspace/")
        req.user = admin
        self.assertEqual(picm_workbench(req).status_code, 403)
        req = rf.post("/picm/logout/")
        req.user = admin
        self.assertEqual(picm_logout(req).status_code, 403)
        req = rf.get("/picm/login/")
        req.user = admin
        self.assertEqual(picm_login(req).status_code, 200)
        # Fail closed if the unique private binding was ever absent.
        (Path(self.temp.name) / ".owner-user-id").unlink()
        owner = get_user_model().objects.get(username="picm-09170000000")
        self.assertFalse(owner_allowed(owner))
        req.user = owner
        self.assertEqual(picm_login(req).status_code, 200)

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
