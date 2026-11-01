"""Synthetic, no-host tests for private cPanel symlink role inventory."""
import json
import unittest
import tempfile
from pathlib import Path

from scripts.mojplaywin_live_link_dependencies_readonly_20261101 import (role_for_target, target_kind, alias_purpose, direct_child_metadata, allowed_private_target_metadata)


class LinkRoleTests(unittest.TestCase):
    SOURCE = "Saeit-staging/sub/alias"

    def test_backed_roots(self):
        self.assertEqual(role_for_target(self.SOURCE, "../../mojplaywin.com/file"),
                         "backed_primary_roots")

    def test_alternate_site_root(self):
        self.assertEqual(role_for_target(self.SOURCE, "../../Saeit/core/file"),
                         "alternative_site_code_root")

    def test_runtime_role(self):
        self.assertEqual(role_for_target(self.SOURCE, "../../virtualenv/app"),
                         "python_runtime_dependency")

    def test_other_unbacked_role(self):
        self.assertEqual(role_for_target(self.SOURCE, "../../other-private/data"),
                         "other_unbacked_account_root")

    def test_outside_account_rejected(self):
        self.assertEqual(role_for_target(self.SOURCE, "/etc/passwd"), "outside_account")
        self.assertEqual(role_for_target(self.SOURCE, "../../../escape"), "outside_account")

    def test_absolute_home_path_not_printed(self):
        self.assertEqual(
            role_for_target(self.SOURCE, "/home/zomorod2/public_html/asset"),
            "alternative_site_code_root")

    def test_target_kind_never_exposes_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            regular = root / "secret-name"
            regular.write_text("synthetic", encoding="utf8")
            self.assertEqual(target_kind(regular), "regular_file")
            self.assertEqual(target_kind(root), "directory")
            self.assertEqual(target_kind(root / "missing"), "missing")



class PrivateShallowTargetMetadataTests(unittest.TestCase):
    def test_alias_purpose_uses_only_fixed_labels(self):
        self.assertEqual(alias_purpose("mojplaywin.com/hidden/media"), "site_asset_alias")
        self.assertEqual(alias_purpose("Saeit-staging/unknown-private"), "unclassified_alias")

    def test_target_direct_children_no_contents_or_private_names(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "secret-customer-007.txt").write_text("CUSTOMER_SECRET_VALUE", encoding="utf8")
            (root / "manage.py").write_text("private project code", encoding="utf8")
            (root / "media").mkdir()
            report = direct_child_metadata(root)
            self.assertEqual(report["direct_child_count"], 3)
            self.assertEqual(report["direct_child_types"], {"directory": 1, "regular_file": 2})
            self.assertEqual(report["fixed_marker_categories"], ["python_project", "website_media"])
            data = json.dumps(report)
            self.assertNotIn("secret-customer", data)
            self.assertNotIn("CUSTOMER_SECRET", data)
            self.assertNotIn(td, data)

    def test_shallow_scan_never_descends_or_follows_nested_link(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "child").mkdir()
            (root / "child" / "wp-config.php").write_text("private", encoding="utf8")
            (root / "alias").symlink_to(root / "child", target_is_directory=True)
            report = direct_child_metadata(root)
            self.assertEqual(report["direct_child_count"], 2)
            self.assertEqual(report["direct_child_types"], {"directory": 1, "symbolic_link": 1})
            self.assertNotIn("php_project", report["fixed_marker_categories"])

    def test_outside_account_and_account_home_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td)
            account = parent / "account"
            account.mkdir()
            outside = parent / "another-account"
            outside.mkdir()
            self.assertEqual(allowed_private_target_metadata(outside, account)["inspection"],
                             "rejected_outside_scoped_account")
            self.assertEqual(allowed_private_target_metadata(account, account)["inspection"],
                             "rejected_outside_scoped_account")

    def test_scoped_same_owner_directory_is_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            account = Path(td)
            dest = account / "extra-private"
            dest.mkdir()
            (dest / "package.json").write_text('{"secret":"not-for-logs"}', encoding="utf8")
            result = allowed_private_target_metadata(dest, account)
            self.assertEqual(result["inspection"], "one_level_completed")
            self.assertEqual(result["metadata"]["fixed_marker_categories"], ["javascript_project"])
            self.assertNotIn("not-for-logs", json.dumps(result))
            self.assertNotIn(td, json.dumps(result))

    def test_large_directories_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a").touch()
            (root / "b").touch()
            with self.assertRaisesRegex(RuntimeError, "TARGET_DIRECTORY_SCAN_LIMIT"):
                direct_child_metadata(root, max_entries=1)


if __name__ == "__main__":
    unittest.main()
