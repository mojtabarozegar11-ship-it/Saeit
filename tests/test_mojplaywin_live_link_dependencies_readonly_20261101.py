"""Synthetic, no-host tests for private cPanel symlink role inventory."""
import unittest

from scripts.mojplaywin_live_link_dependencies_readonly_20261101 import role_for_target


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


if __name__ == "__main__":
    unittest.main()
