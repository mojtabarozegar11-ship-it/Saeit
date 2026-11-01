"""Synthetic, no-host tests for private cPanel symlink role inventory."""
import unittest
import tempfile
from pathlib import Path

from scripts.mojplaywin_live_link_dependencies_readonly_20261101 import (role_for_target, target_kind, source_scope, directory_population)


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


    def test_bounded_source_scope_without_private_names(self):
        self.assertEqual(source_scope("Saeit-staging/a-private/sub/alias"), "application_tree")
        self.assertEqual(source_scope("mojplaywin.com/custom/something"), "public_web_tree")
        self.assertEqual(source_scope("unknown-private/alias"), "outside_primary_roots")
        for name in ("secret-business-name", "a-private", "custom"):
            self.assertNotIn(name, source_scope("Saeit-staging/" + name + "/link"))

    def test_bounded_directory_population_never_returns_names(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertEqual(directory_population(root), "empty")
            (root / "private-name-one").mkdir()
            self.assertEqual(directory_population(root), "one_to_31_entries")
            for i in range(32):
                (root / ("private-data-" + str(i))).mkdir()
            self.assertEqual(directory_population(root), "at_least_32_entries")
            self.assertNotIn("private-name", directory_population(root))

    def test_directory_population_bounds_enforced(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                directory_population(Path(td), 33)
            with self.assertRaises(ValueError):
                directory_population(Path(td), 0)


if __name__ == "__main__":
    unittest.main()
