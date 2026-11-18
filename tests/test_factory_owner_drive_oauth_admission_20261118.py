"""Offline checks of owner OAuth config and dual-Drive capacity.

All fixtures are fabricated placeholders. No remote contact, live tokens,
storage writes, user files or factory services.
"""
import configparser
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from scripts import factory_owner_drive_setup as m


class OwnerOAuthAdmission(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "rclone.conf"
        self.conf = configparser.RawConfigParser()
        for name, root in (("factory_a", m.ROOT_A), ("factory_b", m.ROOT_B)):
            self.conf[name] = {
                "type": "drive",
                "root_folder_id": root,
                "client_id": "fixture-only-123.apps.googleusercontent.com",
                "client_secret": "fake-fixture-never-real",
                "scope": "drive",
                "token": json.dumps({"refresh_token": "fixture-" + name}),
            }

    def validate(self):
        with self.path.open("w") as fp:
            self.conf.write(fp)
        self.path.chmod(0o600)
        return m._validate_owner_oauth_config(self.path)

    def test_distinct_grants_accepted_locally(self):
        self.assertIsNone(self.validate())

    def test_default_client_rejected(self):
        del self.conf["factory_a"]["client_id"]
        with self.assertRaisesRegex(m.TransferHold, "OWNER_DEDICATED"):
            self.validate()

    def test_untrusted_client_id_rejected(self):
        self.conf["factory_a"]["client_id"] = "not-google"
        with self.assertRaisesRegex(m.TransferHold, "OWNER_DEDICATED"):
            self.validate()

    def test_missing_client_secret_rejected(self):
        del self.conf["factory_a"]["client_secret"]
        with self.assertRaisesRegex(m.TransferHold, "OWNER_DEDICATED"):
            self.validate()

    def test_readonly_scope_rejected(self):
        self.conf["factory_b"]["scope"] = "drive.readonly"
        with self.assertRaisesRegex(m.TransferHold, "OWNER_EXISTING"):
            self.validate()

    def test_wrong_root_rejected(self):
        self.conf["factory_b"]["root_folder_id"] = m.ROOT_A
        with self.assertRaisesRegex(m.TransferHold, "OWNER_DRIVE_REMOTE"):
            self.validate()

    def test_sa_override_rejected(self):
        self.conf["factory_a"]["service_account_file"] = "/fixture-only.json"
        with self.assertRaisesRegex(m.TransferHold, "OWNER_EXISTING"):
            self.validate()

    def test_missing_refresh_rejected(self):
        self.conf["factory_b"]["token"] = "{}"
        with self.assertRaisesRegex(m.TransferHold, "OWNER_OFFLINE"):
            self.validate()

    def test_malformed_token_rejected(self):
        self.conf["factory_a"]["token"] = "fixture-invalid"
        with self.assertRaisesRegex(m.TransferHold, "OWNER_OFFLINE"):
            self.validate()

    def test_duplicate_refresh_rejected(self):
        self.conf["factory_b"]["token"] = self.conf["factory_a"]["token"]
        with self.assertRaisesRegex(m.TransferHold, "DUPLICATE_OAUTH"):
            self.validate()

    def test_exact_pair_capacity(self):
        self.assertEqual(m.historical_pair_required_bytes(), 3895227392)

    def test_both_roots_require_pair_capacity(self):
        n = m.historical_pair_required_bytes()
        for a, b, expected in ((n, n, True), (n-1, n, False), (n, n-1, False)):
            with self.subTest(a=a,b=b):
                with patch.object(m,"_validate_owner_oauth_config"), patch.object(m,"RcloneDualStore") as s:
                    s.return_value.preflight.return_value = SimpleNamespace(
                        free_a_before=a,free_b_before=b,proof_readbacks_verified=True)
                    out = m._check(Path("/fixture-rclone"), self.path)
                    self.assertIs(out["historical_pair_capacity_screen_passed"], expected)
                    self.assertFalse(out["google_oauth_publishing_state_verified"])
                    self.assertFalse(out["historical_pair_uploaded"])
