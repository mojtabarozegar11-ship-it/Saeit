"""MOJ Pay Django boundary integration tests; fake credentials, never live funds."""
import json
import os
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone
from banknew.google_identity import GooglePrincipal, GoogleIdentityError
from banknew.models import GoogleAccountLink, LoginChallenge

OIDC_CLIENT = "123456789-abcdef0123456789.apps.googleusercontent.com"
ENV = {"BANKNEW_AUTH_ENABLED": "1", "BANKNEW_GOOGLE_CLIENT_ID": OIDC_CLIENT}
SUB = "109876543210987654321"
TOKEN = "header.payload.signature"


class BoundaryTests(TestCase):
    def setUp(self):
        p = patch.dict(os.environ, ENV)
        p.start()
        self.addCleanup(p.stop)
        self.web = Client(enforce_csrf_checks=True)

    def start_login(self):
        r = self.web.get("/auth/start/")
        self.assertEqual(r.status_code, 200)
        return r.json()

    def sign_in(self, state, *, email="customer@gmail.com"):
        principal = GooglePrincipal(
            subject=SUB, email=email, hosted_domain=None,
            issued_at=100, expires_at=300,
        )
        with patch("banknew.identity_views.verify_google_credential", return_value=principal) as checker:
            result = self.web.post(
                "/auth/finish/",
                data=json.dumps({"credential": TOKEN}),
                content_type="application/json",
                HTTP_X_CSRFTOKEN=state["csrf_token"],
            )
            if result.status_code == 200:
                checker.assert_called_once_with(TOKEN, client_id=OIDC_CLIENT,
                                                expected_nonce=state["nonce"])
        return result

    def test_disabled_by_default_when_flag_or_client_missing(self):
        with patch.dict(os.environ, {"BANKNEW_AUTH_ENABLED": "0"}):
            self.assertEqual(self.web.get("/auth/start/").status_code, 503)
        with patch.dict(os.environ, {"BANKNEW_GOOGLE_CLIENT_ID": ""}):
            self.assertEqual(self.web.get("/auth/start/").status_code, 503)
        self.assertFalse(LoginChallenge.objects.exists())

    def test_challenge_is_session_bound_and_has_no_financial_grants(self):
        s = self.start_login()
        self.assertFalse(s["payments_enabled"])
        self.assertFalse(s["financial_kyc_verified"])
        self.assertEqual(LoginChallenge.objects.count(), 1)
        other = Client()
        self.assertEqual(other.post("/auth/finish/", data=json.dumps({"credential": TOKEN}),
                                    content_type="application/json").status_code, 400)

    def test_csrf_is_required(self):
        self.start_login()
        r = self.web.post("/auth/finish/", data=json.dumps({"credential": TOKEN}),
                          content_type="application/json")
        self.assertEqual(r.status_code, 403)
        self.assertIsNone(LoginChallenge.objects.get().consumed_at)

    def test_success_creates_a_separate_low_privilege_user(self):
        s = self.start_login()
        r = self.sign_in(s)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.json()["financial_kyc_verified"])
        self.assertFalse(r.json()["payments_enabled"])
        link = GoogleAccountLink.objects.select_related("user").get()
        self.assertEqual(link.google_subject, SUB)
        self.assertTrue(link.user.username.startswith("bn_"))
        self.assertFalse(link.user.has_usable_password())
        self.assertFalse(link.user.is_staff or link.user.is_superuser)
        self.assertIsNotNone(LoginChallenge.objects.get().consumed_at)
        me = self.web.get("/auth/session/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["email"], "customer@gmail.com")

    def test_google_email_never_links_existing_account(self):
        old = get_user_model().objects.create_user(
            username="existing", email="customer@gmail.com", password="secret",
        )
        self.assertEqual(self.sign_in(self.start_login()).status_code, 200)
        self.assertNotEqual(GoogleAccountLink.objects.get().user_id, old.pk)

    def test_same_subject_uses_same_user_when_email_changes(self):
        self.assertEqual(self.sign_in(self.start_login()).status_code, 200)
        user_id = GoogleAccountLink.objects.get().user_id
        ses = self.web.session
        ses["mojpay_google_last_start"] = 0
        ses.save()
        self.assertEqual(self.sign_in(self.start_login(), email="new@gmail.com").status_code, 200)
        self.assertEqual(GoogleAccountLink.objects.get().user_id, user_id)
        self.assertEqual(GoogleAccountLink.objects.get().verified_email, "new@gmail.com")
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_replay_rejected_after_success(self):
        state = self.start_login()
        self.assertEqual(self.sign_in(state).status_code, 200)
        r = self.web.post(
            "/auth/finish/", data=json.dumps({"credential": TOKEN}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.web.cookies["csrftoken"].value,
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(GoogleAccountLink.objects.count(), 1)

    def test_expired_challenge_rejected_before_google_verifier(self):
        state = self.start_login()
        LoginChallenge.objects.update(issued_at=timezone.now()-timedelta(minutes=6))
        with patch("banknew.identity_views.verify_google_credential") as verifier:
            result = self.web.post("/auth/finish/", data=json.dumps({"credential": TOKEN}),
                                   content_type="application/json",
                                   HTTP_X_CSRFTOKEN=state["csrf_token"])
            self.assertEqual(result.status_code, 400)
            verifier.assert_not_called()

    def test_failed_verification_consumes_challenge_and_no_user(self):
        state = self.start_login()
        with patch("banknew.identity_views.verify_google_credential",
                   side_effect=GoogleIdentityError("bad signature")):
            r = self.web.post(
                "/auth/finish/", data=json.dumps({"credential": TOKEN}),
                content_type="application/json",
                HTTP_X_CSRFTOKEN=state["csrf_token"],
            )
        self.assertEqual(r.status_code, 401)
        self.assertEqual(get_user_model().objects.count(), 0)
        self.assertIsNotNone(LoginChallenge.objects.get().consumed_at)

    def test_existing_staff_binding_cannot_authenticate(self):
        staff = get_user_model().objects.create_user(
            username="staff", password="secret", is_staff=True,
        )
        GoogleAccountLink.objects.create(
            google_subject=SUB, user=staff, verified_email="customer@gmail.com",
        )
        self.assertEqual(self.sign_in(self.start_login()).status_code, 403)
        self.assertNotIn("_auth_user_id", self.web.session)

    def test_per_session_start_rate_limit_and_csrf_logout(self):
        self.start_login()
        self.assertEqual(self.web.get("/auth/start/").status_code, 429)
        ses = self.web.session
        ses["mojpay_google_last_start"] = 0
        ses.save()
        state = self.start_login()
        self.assertEqual(self.sign_in(state).status_code, 200)
        self.assertEqual(self.web.post("/auth/signout/").status_code, 403)
        self.assertEqual(self.web.post(
            "/auth/signout/", HTTP_X_CSRFTOKEN=self.web.cookies["csrftoken"].value,
        ).status_code, 200)
        self.assertEqual(self.web.get("/auth/session/").status_code, 401)
