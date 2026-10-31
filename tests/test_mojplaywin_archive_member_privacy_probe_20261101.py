"""No-data tests for private backup archive member-category diagnostics."""
import io
import tarfile
import unittest

from scripts.mojplaywin_archive_member_privacy_probe_20261101 import (
    classify_tar, link_category, member_category,
)


class MemberCategoryTests(unittest.TestCase):
    def test_approved_paths(self):
        self.assertEqual(member_category("Saeit-staging/core/settings.py"), "approved_root")
        self.assertEqual(member_category("mojplaywin.com/index.html"), "approved_root")

    def test_dot_prefixed_root_is_rejected_without_path_disclosure(self):
        self.assertEqual(member_category("./Saeit-staging/file.txt"), "dot_prefix")

    def test_unsafe_roots_and_traversal_remain_rejected(self):
        self.assertEqual(member_category("/etc/passwd"), "absolute")
        self.assertEqual(member_category("Saeit-staging/../outside"), "parent_traversal")
        self.assertEqual(member_category("other-tenant/file"), "outside_approved_roots")
        self.assertEqual(member_category(""), "empty_or_invalid")

    def test_tar_metadata_only_and_stream_fully_drained(self):
        output = io.BytesIO()
        names = ("Saeit-staging/data", "./mojplaywin.com/ok",
                 "unrelated-site/private", "mojplaywin.com/static")
        with tarfile.open(fileobj=output, mode="w") as writer:
            for name in names:
                item = tarfile.TarInfo(name)
                item.type = tarfile.DIRTYPE
                writer.addfile(item)
        opaque_footer = b"-- synthetic source footer --"
        stream = io.BytesIO(output.getvalue() + opaque_footer)
        report = classify_tar(stream)
        self.assertEqual(report["member_count_capped"], len(names))
        self.assertEqual(report["tar_read_status"], "PASS")
        self.assertEqual(report["categories"]["approved_root"], 2)
        self.assertEqual(report["categories"]["dot_prefix"], 1)
        self.assertEqual(report["categories"]["outside_approved_roots"], 1)
        self.assertEqual(stream.tell(), len(stream.getvalue()))
        self.assertNotIn("unrelated-site", str(report))
        self.assertNotIn("private", str(report))

    def test_link_target_categories_preserve_tenant_boundary(self):
        self.assertEqual(
            link_category("Saeit-staging/sub/link", "../../outside", True),
            "outside_approved_roots")
        self.assertEqual(
            link_category("Saeit-staging/sub/link", "/etc/passwd", True),
            "unbacked_absolute_symlink")
        self.assertEqual(
            link_category("Saeit-staging/sub/link",
                          "/home/zomorod2/mojplaywin.com/file", True),
            "inside_approved_roots")
        self.assertEqual(
            link_category("Saeit-staging/hard", "/etc/passwd", False),
            "absolute_hardlink_rejected")

    def test_link_tar_metadata_summary_never_reveals_target(self):
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w") as writer:
            for name, target, kind in (
                ("Saeit-staging/symlink", "../../../secret-link-target",
                 tarfile.SYMTYPE),
                ("mojplaywin.com/hardlink", "Saeit-staging/data",
                 tarfile.LNKTYPE),
            ):
                item = tarfile.TarInfo(name)
                item.type = kind
                item.linkname = target
                writer.addfile(item)
        report = classify_tar(io.BytesIO(output.getvalue()))
        self.assertEqual(report["link_target_categories"][
            "symlink_parent_traversal"], 1)
        self.assertEqual(report["link_target_categories"][
            "hardlink_inside_approved_roots"], 1)
        self.assertNotIn("secret-link-target", str(report))


if __name__ == "__main__":
    unittest.main()
