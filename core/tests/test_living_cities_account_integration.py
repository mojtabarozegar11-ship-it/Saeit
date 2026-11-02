"""MojPlayWin account game integration on the existing Django user/session database."""
import json
from datetime import timedelta
from unittest.mock import patch

from django.db import DatabaseError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import Resolver404, resolve

from apps.living_cities.models import LoginAttemptBucket, PlayerTycoon, TycoonActionReceipt


@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "zomorodmelal.ir", "testserver"])
class MojPlayWinLivingCitiesAccountTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.player = users.objects.create_user(
            username="mpw_existing_player", password="existing-account-password"
        )
        self.other = users.objects.create_user(
            username="mpw_other_player", password="other-account-password"
        )

    def test_game_api_is_on_mojplaywin_only_and_moj1_remains_paused(self):
        public = self.client.get(
            "/api/living-cities/rewards/moj1-policy/", HTTP_HOST="mojplaywin.com"
        )
        self.assertEqual(public.status_code, 200, public.content)
        policy = public.json()
        self.assertEqual(policy["symbol"], "MOJ1")
        self.assertEqual(policy["network"], "TRON")
        self.assertIs(policy["recipient_payout_enabled"], False)
        self.assertIs(policy["independent_audit_verified"], False)

        for path in (
            "/api/living-cities/rewards/moj1-policy/",
            "/api/living-cities/tycoon/",
            "/api/living-cities/auth/login/",
        ):
            denied = self.client.get(path, HTTP_HOST="zomorodmelal.ir")
            self.assertEqual(denied.status_code, 404, path)

        with self.assertRaises(Resolver404):
            resolve("/living-cities/play/")  # Existing static game is untouched.

    def test_existing_django_account_owns_independent_server_business_state(self):
        self.assertEqual(
            self.client.get("/api/living-cities/tycoon/", HTTP_HOST="mojplaywin.com").status_code,
            401,
        )
        self.client.force_login(self.player)
        mine = self.client.get("/api/living-cities/tycoon/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(mine.status_code, 200, mine.content)
        self.assertEqual(mine.json()["authority"], "server")
        self.assertEqual(len(mine.json()["state"]["businessLevels"]), 20)
        self.assertEqual(mine.json()["state"]["businessLevels"]["bakery"], 1)
        self.assertEqual(PlayerTycoon.objects.filter(owner=self.player).count(), 1)

        self.client.force_login(self.other)
        other = self.client.get("/api/living-cities/tycoon/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(other.status_code, 200)
        self.assertEqual(other.json()["state"]["coins"], 320)
        self.assertEqual(PlayerTycoon.objects.count(), 2)

    def test_csrf_rotates_on_login_then_first_upgrade_and_logout_work(self):
        browser = Client(enforce_csrf_checks=True)
        page = browser.get("/api/living-cities/auth/csrf/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(page.status_code, 200, page.content)
        self.assertEqual(page["Cache-Control"], "private, no-store")
        before_login = page.json()["csrf_token"]
        self.assertRegex(before_login, r"^[A-Za-z0-9]{64}$")
        self.assertIn("csrftoken", page.cookies)
        credentials = json.dumps({
            "username": "mpw_existing_player",
            "password": "existing-account-password",
        })

        missing = browser.post(
            "/api/living-cities/auth/login/", credentials,
            content_type="application/json", HTTP_HOST="mojplaywin.com",
        )
        self.assertEqual(missing.status_code, 403)

        login = browser.post(
            "/api/living-cities/auth/login/", credentials,
            content_type="application/json", HTTP_HOST="mojplaywin.com",
            HTTP_X_CSRFTOKEN=before_login,
        )
        self.assertEqual(login.status_code, 200, login.content)
        self.assertTrue(login.json()["authenticated"])
        self.assertEqual(login["Cache-Control"], "private, no-store")
        fresh = login.json()["csrf_token"]
        self.assertRegex(fresh, r"^[A-Za-z0-9]{64}$")
        self.assertNotEqual(fresh, before_login)
        self.assertIn("csrftoken", login.cookies)

        action = json.dumps({
            "action": {"type": "upgrade", "business_id": "bakery"},
            "idempotency_key": "mpw-csrf-game-action-0001",
        })
        stale = browser.post(
            "/api/living-cities/tycoon/actions/", action,
            content_type="application/json", HTTP_HOST="mojplaywin.com",
            HTTP_X_CSRFTOKEN=before_login,
        )
        self.assertEqual(stale.status_code, 403)
        upgraded = browser.post(
            "/api/living-cities/tycoon/actions/", action,
            content_type="application/json", HTTP_HOST="mojplaywin.com",
            HTTP_X_CSRFTOKEN=fresh,
        )
        self.assertEqual(upgraded.status_code, 200, upgraded.content)
        self.assertEqual(upgraded.json()["state"]["businessLevels"]["bakery"], 2)
        self.assertEqual(TycoonActionReceipt.objects.count(), 1)

        replay = browser.post(
            "/api/living-cities/tycoon/actions/", action,
            content_type="application/json", HTTP_HOST="mojplaywin.com",
            HTTP_X_CSRFTOKEN=fresh,
        )
        self.assertEqual(replay.status_code, 200, replay.content)
        self.assertTrue(replay.json()["replayed"])
        self.assertEqual(TycoonActionReceipt.objects.count(), 1)

        blocked_logout = browser.post(
            "/api/living-cities/auth/logout/", HTTP_HOST="mojplaywin.com"
        )
        self.assertEqual(blocked_logout.status_code, 403)
        logout = browser.post(
            "/api/living-cities/auth/logout/", HTTP_HOST="mojplaywin.com",
            HTTP_X_CSRFTOKEN=fresh,
        )
        self.assertEqual(logout.status_code, 200, logout.content)
        self.assertFalse(logout.json()["authenticated"])
        self.assertEqual(
            browser.get("/api/living-cities/tycoon/", HTTP_HOST="mojplaywin.com").status_code,
            401,
        )

    def test_invalid_password_burst_is_limited_across_clients_on_same_ip(self):
        browser = Client(enforce_csrf_checks=True)
        token = browser.get(
            "/api/living-cities/auth/csrf/", HTTP_HOST="mojplaywin.com"
        ).json()["csrf_token"]
        endpoint = "/api/living-cities/auth/login/"
        bad = json.dumps({"username": "mpw_existing_player", "password": "incorrect"})
        statuses = [
            browser.post(
                endpoint, bad, content_type="application/json",
                HTTP_HOST="mojplaywin.com", HTTP_X_CSRFTOKEN=token,
            ).status_code
            for _ in range(5)
        ]
        self.assertEqual(statuses, [401, 401, 401, 401, 429])
        blocked = LoginAttemptBucket.objects.get(blocked_until__isnull=False)
        self.assertEqual(len(blocked.key_digest), 64)
        self.assertNotIn("mpw_existing_player", blocked.key_digest)
        self.assertEqual(blocked.failures, 5)

        good = json.dumps({
            "username": "mpw_existing_player", "password": "existing-account-password"
        })
        denied = browser.post(
            endpoint, good, content_type="application/json",
            HTTP_HOST="mojplaywin.com", HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(denied.status_code, 429)
        self.assertEqual(denied["Retry-After"], "900")
        self.assertEqual(browser.get(
            "/api/living-cities/auth/me/", HTTP_HOST="mojplaywin.com"
        ).status_code, 401)

        # Distinct remote address has its own bucket, without trusting XFF.
        other = Client(enforce_csrf_checks=True)
        other_token = other.get(
            "/api/living-cities/auth/csrf/", HTTP_HOST="mojplaywin.com",
            REMOTE_ADDR="192.0.2.7",
        ).json()["csrf_token"]
        allowed = other.post(
            endpoint, good, content_type="application/json",
            HTTP_HOST="mojplaywin.com", HTTP_X_CSRFTOKEN=other_token,
            REMOTE_ADDR="192.0.2.7", HTTP_X_FORWARDED_FOR="127.0.0.1",
        )
        self.assertEqual(allowed.status_code, 200, allowed.content)

        blocked.blocked_until = timezone.now() - timedelta(seconds=1)
        blocked.first_failure_at = timezone.now() - timedelta(minutes=16)
        blocked.save(update_fields=["blocked_until", "first_failure_at"])
        recovered = browser.post(
            endpoint, good, content_type="application/json",
            HTTP_HOST="mojplaywin.com", HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(recovered.status_code, 200, recovered.content)

    def test_unavailable_shared_throttle_fails_closed(self):
        browser = Client(enforce_csrf_checks=True)
        token = browser.get(
            "/api/living-cities/auth/csrf/", HTTP_HOST="mojplaywin.com"
        ).json()["csrf_token"]
        with patch(
            "apps.living_cities.auth_api._authenticate_with_throttle",
            side_effect=DatabaseError("unavailable"),
        ):
            response = browser.post(
                "/api/living-cities/auth/login/",
                json.dumps({
                    "username": "mpw_existing_player",
                    "password": "existing-account-password",
                }),
                content_type="application/json", HTTP_HOST="mojplaywin.com",
                HTTP_X_CSRFTOKEN=token,
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(browser.get(
            "/api/living-cities/auth/me/", HTTP_HOST="mojplaywin.com"
        ).status_code, 401)
