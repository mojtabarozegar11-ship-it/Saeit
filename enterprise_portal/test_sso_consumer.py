"""Fail-closed Django endpoint tests using isolated TestCase database and synthetic secrets."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import tempfile
import time
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

from .models import OfficeSsoIdentity, OfficeSsoNonce

ORIGIN = "https://zomorodmelal.ir"
URL = "/company/office/sso/consume/"
STEP = "/company/office/sso/otp/"


def signed_ticket(uid=42, role="admin", secret=b"K" * 32, now=None, nonce=None):
    at = int(time.time()) if now is None else now
    data = {
        "iss": "zomorod-business-php", "aud": "zomorod-company-office",
        "iat": at, "exp": at + 30,
        "nonce": base64.urlsafe_b64encode(nonce or secrets.token_bytes(16)).rstrip(b"=").decode(),
        "uid": uid, "role": role,
    }
    body = base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).rstrip(b"=").decode()
    signed = "v1." + body
    mac = base64.urlsafe_b64encode(hmac.new(secret, signed.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    return signed + "." + mac


@override_settings(
    DEBUG=False, ALLOWED_HOSTS=["testserver", "zomorodmelal.ir"],
    COMPANY_OFFICE_REQUIRE_MFA=True,
    STORAGES={"default":{"BACKEND":"django.core.files.storage.FileSystemStorage"},"staticfiles":{"BACKEND":"django.contrib.staticfiles.storage.StaticFilesStorage"}},
    COMPANY_OFFICE_SSO_ENABLED=True,
)
class OfficeSsoConsumerTests(TestCase):
    def setUp(self):
        self.keydir = tempfile.TemporaryDirectory()
        self.addCleanup(self.keydir.cleanup)
        path = Path(self.keydir.name) / "private.key"
        path.write_bytes(b"K" * 32)
        path.chmod(0o600)
        self.override = override_settings(COMPANY_OFFICE_SSO_KEY_PATH=str(path))
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.user = get_user_model().objects.create_user(
            username="mapped-clerk", password=None, is_staff=True, is_active=True,
        )
        right = Permission.objects.get(
            content_type__app_label="enterprise_portal", codename="view_businessunit",
        )
        self.user.user_permissions.add(right)
        self.mapping = OfficeSsoIdentity.objects.create(
            php_uid=42, user=self.user, role="admin", active=True,
        )
        self.device = TOTPDevice.objects.create(
            user=self.user, name="test device", confirmed=True,
        )

    def post(self, ticket, *, secure=True, origin=ORIGIN):
        return self.client.post(URL, {"ticket": ticket}, secure=secure, HTTP_ORIGIN=origin)

    def test_one_use_ticket_starts_unverified_short_session_only(self):
        ticket = signed_ticket()
        response = self.post(ticket)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], STEP)
        self.assertEqual(OfficeSsoNonce.objects.count(), 1)
        self.assertEqual(self.client.session.get("zm_sso_php_uid"), 42)
        self.assertEqual(self.client.session.get("_auth_user_id"), str(self.user.pk))
        blocked = self.client.get("/company/office/messages/", secure=True)
        self.assertEqual(blocked.status_code, 302)
        self.assertIn("/company/office/secure-login/", blocked["Location"])
        self.assertEqual(self.post(ticket).status_code, 403)
        self.assertEqual(OfficeSsoNonce.objects.count(), 1)

    def test_mfa_step_up_only_requests_confirmed_otp_and_opens_dashboard(self):
        self.assertEqual(self.post(signed_ticket()).status_code, 302)
        page = self.client.get(STEP, secure=True)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "کد یک‌بارمصرف")
        code = str(totp(self.device.bin_key)).zfill(self.device.digits)
        reply = self.client.post(STEP, {
            "otp_device": self.device.persistent_id,
            "otp_token": code,
        }, secure=True)
        self.assertEqual(reply.status_code, 302)
        self.assertEqual(reply["Location"], "/company/office/")
        self.assertNotIn("zm_sso_pending", self.client.session)
        self.assertEqual(self.client.get("/company/office/", secure=True).status_code, 200)

    def test_disabled_by_default_is_404_and_creates_no_nonce(self):
        with override_settings(COMPANY_OFFICE_SSO_ENABLED=False):
            self.assertEqual(self.post(signed_ticket()).status_code, 404)
        self.assertEqual(OfficeSsoNonce.objects.count(), 0)

    def test_unauthenticated_otp_step_up_rejected(self):
        self.assertEqual(self.client.get(STEP, secure=True).status_code, 403)

    def test_missing_origin_and_plain_http_are_rejected_before_database_write(self):
        self.assertEqual(self.post(signed_ticket(), origin="https://attacker.example").status_code, 403)
        self.assertEqual(self.post(signed_ticket(), secure=False).status_code, 403)
        self.assertEqual(OfficeSsoNonce.objects.count(), 0)

    def test_only_form_post_is_accepted(self):
        self.assertEqual(self.client.get(URL, secure=True).status_code, 405)
        self.assertEqual(OfficeSsoNonce.objects.count(), 0)

    def test_unapproved_mapping_cannot_login(self):
        self.mapping.active = False
        self.mapping.save(update_fields=["active"])
        self.assertEqual(self.post(signed_ticket()).status_code, 403)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_role_downgrade_mismatch_is_rejected(self):
        self.assertEqual(self.post(signed_ticket(role="accountant")).status_code, 403)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_no_otp_device_denies_sso_without_login(self):
        self.device.delete()
        self.assertEqual(self.post(signed_ticket()).status_code, 403)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_nonstaff_user_does_not_gain_staff_from_ticket(self):
        self.user.is_staff = False
        self.user.save(update_fields=["is_staff"])
        self.assertEqual(self.post(signed_ticket()).status_code, 403)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)

    def test_wrong_hmac_is_rejected(self):
        self.assertEqual(self.post(signed_ticket(secret=b"Z" * 32)).status_code, 403)
        self.assertEqual(OfficeSsoNonce.objects.count(), 0)

    def test_old_ticket_is_rejected(self):
        self.assertEqual(self.post(signed_ticket(now=int(time.time()) - 60)).status_code, 403)
        self.assertEqual(OfficeSsoNonce.objects.count(), 0)
