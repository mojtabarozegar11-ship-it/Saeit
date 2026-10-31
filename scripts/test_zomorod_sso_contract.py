"""Offline cross-language regression tests; never touch production hosts or databases."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from enterprise_portal.sso_contract import SSOTicketError, verify_ticket

KEY = b"K" * 32
NOW = 1700000000
PHP_FILE = ROOT / "content" / "zomorod-business" / "office_sso_ticket.php"


def issue_php(uid=42, role="admin", key="K"):
    code = (
        'require $argv[1]; '
        'echo zmOfficeSsoIssue((int)$argv[2], $argv[3], str_repeat($argv[4], 32), 1700000000);'
    )
    done = subprocess.run(
        ["php", "-r", code, "--", str(PHP_FILE), str(uid), role, key],
        cwd=ROOT, capture_output=True, text=True, timeout=15,
    )
    if done.returncode:
        raise RuntimeError("PHP test issuer failed")
    return done.stdout


def resign(data, *, secret=KEY):
    payload = base64.urlsafe_b64encode(
        json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode()
    ).rstrip(b"=").decode()
    signed = "v1." + payload
    signature = base64.urlsafe_b64encode(
        hmac.new(secret, signed.encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    return signed + "." + signature


def claims(token):
    part = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


class CrossLanguageTicketTests(unittest.TestCase):
    def setUp(self):
        self.seen = set()

    def consume(self, nonce_hash, expires):
        if nonce_hash in self.seen:
            return False
        self.seen.add(nonce_hash)
        return True

    def verify(self, token, **kw):
        return verify_ticket(
            token, KEY, consume_nonce=self.consume, now=NOW, **kw
        )

    def test_php_ticket_is_accepted_by_python_once(self):
        token = issue_php()
        self.assertEqual(
            self.verify(token),
            {"uid": 42, "role": "admin", "iat": NOW, "exp": NOW + 30},
        )
        with self.assertRaises(SSOTicketError):
            self.verify(token)

    def test_distinct_php_tickets_have_random_nonces(self):
        a, b = issue_php(), issue_php()
        self.assertNotEqual(a, b)
        self.verify(a)
        self.verify(b)

    def test_allowed_roles_are_bound_to_ticket(self):
        for role in ("admin", "accountant", "manager"):
            with self.subTest(role=role):
                self.assertEqual(self.verify(issue_php(role=role))["role"], role)

    def test_php_refuses_viewer_and_zero_identity(self):
        for uid, role in ((42, "viewer"), (0, "admin")):
            with self.subTest(uid=uid, role=role):
                code = (
                    'require $argv[1]; '
                    'try { zmOfficeSsoIssue((int)$argv[2], $argv[3], str_repeat("K",32), 1700000000);'
                    ' echo "UNEXPECTED"; } catch (InvalidArgumentException $e) { echo "REJECTED"; }'
                )
                result = subprocess.run(
                    ["php", "-r", code, "--", str(PHP_FILE), str(uid), role],
                    cwd=ROOT, capture_output=True, text=True, timeout=15, check=True,
                )
                self.assertEqual(result.stdout, "REJECTED")

    def test_modified_signature_is_rejected(self):
        token = issue_php()
        signed, payload, sig = token.split(".")
        altered = sig[:-1] + ("A" if sig[-1] != "A" else "B")
        with self.assertRaises(SSOTicketError):
            self.verify(".".join((signed, payload, altered)))

    def test_signed_wrong_audience_and_role_are_rejected(self):
        base = claims(issue_php())
        for field, value in (("aud", "public"), ("iss", "other"), ("role", "viewer"), ("uid", 0)):
            with self.subTest(field=field):
                altered = dict(base, **{field: value})
                with self.assertRaises(SSOTicketError):
                    self.verify(resign(altered))

    def test_expired_and_future_tickets_are_rejected(self):
        original = claims(issue_php())
        variants = (
            dict(original, iat=NOW - 60, exp=NOW - 30),
            dict(original, iat=NOW + 6, exp=NOW + 36),
            dict(original, iat=NOW, exp=NOW + 300),
        )
        for variant in variants:
            with self.assertRaises(SSOTicketError):
                self.verify(resign(variant))

    def test_missing_atomic_replay_consumer_fails_closed(self):
        with self.assertRaises(SSOTicketError):
            verify_ticket(issue_php(), KEY, consume_nonce=None, now=NOW)

    def test_short_key_is_rejected(self):
        with self.assertRaises(SSOTicketError):
            verify_ticket(issue_php(), b"short", consume_nonce=self.consume, now=NOW)

    def test_duplicate_json_claim_is_rejected_even_if_signed(self):
        base = claims(issue_php())
        raw = (
            '{"iss":"zomorod-business-php","iss":"other",'
            '"aud":"zomorod-company-office","iat":1700000000,"exp":1700000030,'
            '"nonce":"' + base["nonce"] + '","uid":42,"role":"admin"}'
        ).encode()
        body = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
        signed = "v1." + body
        signature = base64.urlsafe_b64encode(
            hmac.new(KEY, signed.encode(), hashlib.sha256).digest()
        ).rstrip(b"=").decode()
        with self.assertRaises(SSOTicketError):
            self.verify(signed + "." + signature)

    def test_invalid_nonce_format_is_rejected(self):
        data = claims(issue_php())
        data["nonce"] = "A"
        with self.assertRaises(SSOTicketError):
            self.verify(resign(data))

    def test_unknown_version_and_query_style_are_rejected(self):
        token = issue_php()
        for candidate in ("v2" + token[2:], token + "?next=/", ""):
            with self.assertRaises(SSOTicketError):
                self.verify(candidate)


if __name__ == "__main__":
    unittest.main()
