"""Synthetic, no-host tests for private cPanel symlink role inventory."""
import json
import unittest
import tempfile
from pathlib import Path

from scripts.mojplaywin_live_link_dependencies_readonly_20261101 import (role_for_target, target_kind, alias_purpose, direct_child_metadata, allowed_private_target_metadata, target_site_affinity, bounded_asset_tree_metadata)


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
        self.assertEqual(alias_purpose("mojplaywin.com/hidden/media"), "media_alias")
        self.assertEqual(alias_purpose("mojplaywin.com/static"), "static_alias")
        self.assertEqual(alias_purpose("mojplaywin.com/assets"), "assets_alias")
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

    def test_site_affinity_is_only_hint_and_leaks_no_target_name(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            home = root / "account"
            home.mkdir()
            known = home / "Saeit" / "private-assets"
            known.mkdir(parents=True)
            unknown = home / "unrelated-customer-project" / "media"
            unknown.mkdir(parents=True)
            a = target_site_affinity(known, home)
            b = target_site_affinity(unknown, home)
            self.assertEqual(a, {"hint": "known_site_named_root", "depth": 2})
            self.assertEqual(b, {"hint": "unverified_account_root", "depth": 2})
            self.assertNotIn("unrelated-customer-project", json.dumps(b))
            self.assertNotIn(td, json.dumps(a))

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

    def test_bounded_tree_metadata_only_reports_fixed_file_shapes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "nested-private").mkdir()
            (root / "nested-private" / "customer-secret.css").write_text("SECRET_BYTES", encoding="utf8")
            (root / ".env").write_text("DATABASE_PASSWORD=TOP_SECRET", encoding="utf8")
            (root / "photo.jpg").write_bytes(b"synthetic")
            (root / "main.py").write_text("synthetic", encoding="utf8")
            (root / "alias").symlink_to(root / "nested-private", target_is_directory=True)
            report = bounded_asset_tree_metadata(root)
            self.assertEqual(report["entry_count"], 6)
            self.assertEqual(report["entry_shapes"], {
                "directory": 1, "media_file_shape": 1, "nested_symlink": 1,
                "sensitive_or_backup_file_shape": 1, "source_code_file_shape": 1,
                "web_asset_file_shape": 1,
            })
            self.assertEqual(report["hidden_entry_count"], 1)
            self.assertTrue(report["walk_completed_without_following_links"])
            self.assertFalse(report["file_contents_read"])
            data = json.dumps(report)
            for private in (td, "customer-secret", "DATABASE_PASSWORD", "TOP_SECRET"):
                self.assertNotIn(private, data)

    def test_precompressed_asset_sidecar_requires_ordinary_web_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "app.css").write_text("synthetic stylesheet", encoding="utf8")
            (root / "app.css.gz").write_bytes(b"synthetic compressed")
            (root / "unknown.tar").write_bytes(b"synthetic archive")
            (root / "private.bin.br").write_bytes(b"synthetic brotli")
            result = bounded_asset_tree_metadata(root)
            self.assertEqual(result["entry_shapes"]["precompressed_web_sidecar_shape"], 1)
            self.assertEqual(result["entry_shapes"]["download_archive_shape"], 1)
            self.assertEqual(result["entry_shapes"]["other_gzip_or_brotli_shape"], 1)
            self.assertNotIn("private.bin", json.dumps(result))

    def test_bounded_tree_scan_fails_on_entry_limit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "first.css").touch()
            (root / "second.jpg").touch()
            with self.assertRaisesRegex(RuntimeError, "TARGET_TREE_SCAN_LIMIT"):
                bounded_asset_tree_metadata(root, max_entries=1)

    def test_large_directories_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a").touch()
            (root / "b").touch()
            with self.assertRaisesRegex(RuntimeError, "TARGET_DIRECTORY_SCAN_LIMIT"):
                direct_child_metadata(root, max_entries=1)


if __name__ == "__main__":
    unittest.main()
