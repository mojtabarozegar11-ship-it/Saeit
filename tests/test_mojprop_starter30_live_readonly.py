"""Isolated tests: private-host read-only evidence never becomes release approval."""
from __future__ import annotations
import json
import os
from pathlib import Path
import pwd
import tempfile
import unittest
from unittest.mock import patch

from scripts import mojprop_starter30_live_readonly as probe


class Starter30LiveReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.root = self.home / "mojplaywin.com"
        self.route = self.root / "moj-prop"
        self.package = self.route / "starter-30-trx"
        self.package.mkdir(parents=True)
        self.who = pwd.getpwuid(os.geteuid()).pw_name

    def report(self):
        return probe.snapshot(self.root, owner=self.who)

    def put(self, name, content):
        (self.package / name).write_bytes(content)

    def test_python38_runner_source_uses_compatible_path_guard(self):
        from inspect import getsource
        body = getsource(probe._safe_content)
        self.assertNotIn(".is_relative_to(", body)
        self.assertIn(".relative_to(", body)

    def test_path_outside_the_owner_docroot_is_not_read(self):
        external = self.home / "private-data.txt"
        external.write_bytes(b"never read unrelated directory")
        self.assertIsNone(probe._safe_content(self.root, external))

    def test_json_serialisable(self):
        json.dumps(self.report())

    def test_schema_is_versioned(self):
        self.assertEqual(self.report()["schema"], "mojprop.starter30.live_readonly.v1")

    def test_read_only_guarantee(self):
        result = self.report()
        self.assertIs(result["read_only"], True)
        self.assertIs(result["release_permitted"], False)

    def test_never_claim_revenue_from_source(self):
        result = self.report()
        self.assertIs(result["revenue_proven"], False)
        self.assertIs(result["customer_specific_invoice_and_solidified_settlement"], False)

    def test_no_restore_claim_from_file_metadata(self):
        self.assertIs(self.report()["independent_backup_restored_in_isolation"], False)

    def test_cannot_claim_tenant_isolation(self):
        self.assertIs(self.report()["domain_tenant_isolation_proven"], False)

    def test_without_files_none_are_readable(self):
        self.assertFalse(any(a["readable"] for a in self.report()["assets"].values()))

    def test_created_source_files_are_readable(self):
        self.put("index.html", b"No funded account is included; Payment not enabled; Do not send TRX; 30 TRX")
        self.put("journal-template.csv", b"session,closing_equity_usd,risk_plan_recorded,reflection_recorded\n1,,,\n")
        self.put("journal-guide.txt", b"Education only, not a funded challenge.")
        result = self.report()
        self.assertTrue(all(a["readable"] for a in result["assets"].values()))
        self.assertTrue(result["product_content"]["payment_disabled"])
        self.assertTrue(result["product_content"]["educational_only"])
        self.assertTrue(result["product_content"]["free_journal_valid_shape"])
        self.assertIs(result["release_permitted"], False)

    def test_public_home_and_catalog_links_are_independently_checked(self):
        (self.route / "index.html").write_text("starter-30-trx")
        (self.route / "catalog").mkdir()
        (self.route / "catalog/index.html").write_text("starter-30-trx")
        self.assertTrue(self.report()["product_content"]["linked_from_home"])
        self.assertTrue(self.report()["product_content"]["linked_from_catalog"])

    def test_missing_catalog_link_is_not_assumed(self):
        (self.route / "index.html").write_text("starter-30-trx")
        self.assertFalse(self.report()["product_content"]["linked_from_catalog"])

    def test_symlink_file_denied(self):
        external = self.home / "other"
        external.write_text("30 TRX")
        (self.package / "index.html").symlink_to(external)
        self.assertFalse(self.report()["assets"]["index.html"]["readable"])

    def test_symlink_package_denied(self):
        self.package.rmdir()
        external = self.home / "another"
        external.mkdir()
        (self.route / "starter-30-trx").symlink_to(external)
        result = self.report()
        self.assertFalse(result["docroot_and_route_ownership_verified"])
        self.assertFalse(result["assets"]["index.html"]["readable"])

    def test_wrong_owner_account_denied(self):
        x = probe.snapshot(self.root, owner="impossible-account-name")
        self.assertFalse(x["owner_account_verified"])
        self.assertFalse(x["docroot_and_route_ownership_verified"])

    def test_world_writable_route_denied(self):
        self.route.chmod(0o777)
        self.addCleanup(self.route.chmod, 0o755)
        self.assertFalse(self.report()["docroot_and_route_ownership_verified"])

    def test_missing_root_denied(self):
        result = probe.snapshot(self.home / "notexist", owner=self.who)
        self.assertFalse(result["docroot_and_route_ownership_verified"])

    def test_oversized_asset_not_read(self):
        self.put("index.html", b"x" * (probe.MAX_FILE_BYTES + 1))
        self.assertFalse(self.report()["assets"]["index.html"]["readable"])

    def test_sha_prefix_does_not_disclose_file_content(self):
        self.put("journal-guide.txt", b"secret-like contents are not printed")
        result = self.report()
        serial = json.dumps(result)
        self.assertNotIn("secret-like", serial)
        self.assertEqual(len(result["assets"]["journal-guide.txt"]["sha256_prefix"]), 16)

    def test_does_not_print_sensitive_absolute_paths(self):
        raw = json.dumps(self.report())
        self.assertNotIn(str(self.home), raw)
        self.assertNotIn(str(self.root), raw)

    def test_late_missing_file_not_crash(self):
        self.put("journal-guide.txt", b"hi")
        (self.package / "journal-guide.txt").unlink()
        self.assertFalse(self.report()["assets"]["journal-guide.txt"]["readable"])

    def test_no_file_writes_from_snapshot(self):
        before = sorted(str(p.relative_to(self.home)) for p in self.home.rglob("*"))
        self.report()
        after = sorted(str(p.relative_to(self.home)) for p in self.home.rglob("*"))
        self.assertEqual(before, after)

    def test_synthetic_html_cannot_enable_payment(self):
        self.put("index.html", b"30 TRX; send now")
        self.assertFalse(self.report()["product_content"]["payment_disabled"])

    def test_case_ambiguity_denies_payment(self):
        self.put("index.html", b"payment NOT enabled\ndo not send trx")
        self.assertFalse(self.report()["product_content"]["payment_disabled"])

    def test_non_regular_directory_cannot_serve_asset(self):
        (self.package / "journal-template.csv").mkdir()
        self.assertFalse(self.report()["assets"]["journal-template.csv"]["readable"])

    def test_unknown_merchant_always_blocked(self):
        self.put("index.html", b"30 TRX")
        self.assertFalse(self.report()["approved_verified_trx_merchant"])

    def test_effective_http_route_unknown_from_disk(self):
        self.assertFalse(self.report()["effective_http_route_verified"])


if __name__ == "__main__":
    unittest.main()
