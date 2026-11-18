"""No-overwrite atomic B2B scope: synthetic local filesystem only."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from scripts.zomorod_b2b_create_only_release_20261118 import (
    install_verified, preflight, rollback_verified, verify_installed,
)
from scripts.zomorod_b2b_static_package_20261118 import HERE

SOURCE = "da5edd2bf37233b43a2ca76028a4dbe2ee2160ff"
RUN = "44249493818"

class CreateOnlyB2BReleaseTests(unittest.TestCase):
    def setUp(self):
        self.ctx=tempfile.TemporaryDirectory()
        self.home=Path(self.ctx.name)
        (self.home/"public_html").mkdir()
        (self.home/"public_html"/"index.html").write_text("ORIGINAL HOMEPAGE")
        (self.home/"public_html"/"faremah").mkdir()
        (self.home/"public_html"/"faremah"/"index.html").write_text("ORIGINAL FAREMAH")

    def tearDown(self):
        self.ctx.cleanup()

    def publish(self):
        return install_verified(self.home,HERE,SOURCE,RUN,
            owner_authorization=f"owner-create-only-b2b:{SOURCE}:{RUN}",
            require_owner=False)

    def test_preflight_is_readonly_and_does_not_claim_site_health(self):
        before=(self.home/"public_html"/"index.html").read_bytes()
        status=preflight(self.home,False)
        self.assertTrue(status["create_only_target_absent"])
        self.assertFalse(status["backup_or_http_verified"])
        self.assertEqual(before,(self.home/"public_html"/"index.html").read_bytes())

    @unittest.skipUnless(os.name=="posix","atomic renameat2 requires Linux")
    def test_install_verify_and_explicit_rollback_only_owned_files(self):
        self.assertTrue(self.publish()["created_only"])
        self.assertTrue(verify_installed(self.home,SOURCE,RUN,require_owner=False))
        result=rollback_verified(self.home,SOURCE,RUN,
            owner_authorization=f"owner-rollback-b2b:{SOURCE}:{RUN}",
            require_owner=False)
        self.assertTrue(result["rolled_back_only_owned_created_files"])
        self.assertFalse((self.home/"public_html"/"b2b").exists())
        self.assertEqual((self.home/"public_html"/"index.html").read_text(),"ORIGINAL HOMEPAGE")
        self.assertEqual((self.home/"public_html"/"faremah"/"index.html").read_text(),"ORIGINAL FAREMAH")

    def test_preexisting_target_refused_without_change(self):
        (self.home/"public_html"/"b2b").mkdir()
        (self.home/"public_html"/"b2b"/"index.html").write_text("SOMEONE ELSE'S SITE")
        with self.assertRaises(FileExistsError):
            self.publish()
        self.assertEqual((self.home/"public_html"/"b2b"/"index.html").read_text(),"SOMEONE ELSE'S SITE")

    def test_without_owner_authorization_write_rejected(self):
        with self.assertRaises(PermissionError):
            install_verified(self.home,HERE,SOURCE,RUN,owner_authorization="",
                             require_owner=False)
        self.assertFalse((self.home/"public_html"/"b2b").exists())

    def test_wrong_owner_refused(self):
        with self.assertRaises(PermissionError):
            preflight(self.home,True)

    @unittest.skipUnless(os.name=="posix","atomic renameat2 requires Linux")
    def test_foreign_file_blocks_rollback(self):
        self.publish()
        (self.home/"public_html"/"b2b"/"outside.txt").write_text("other person's content")
        with self.assertRaises(RuntimeError):
            rollback_verified(self.home,SOURCE,RUN,
                owner_authorization=f"owner-rollback-b2b:{SOURCE}:{RUN}",
                require_owner=False)
        self.assertTrue((self.home/"public_html"/"b2b"/"outside.txt").exists())

    @unittest.skipUnless(os.name=="posix","atomic renameat2 requires Linux")
    def test_tampering_blocks_rollback(self):
        self.publish()
        (self.home/"public_html"/"b2b"/"index.html").write_text("CHANGED")
        with self.assertRaises(RuntimeError):
            rollback_verified(self.home,SOURCE,RUN,
                owner_authorization=f"owner-rollback-b2b:{SOURCE}:{RUN}",
                require_owner=False)

    @unittest.skipUnless(os.name=="posix","atomic renameat2 requires Linux")
    def test_forged_marker_cannot_admit_rewritten_public_page(self):
        self.publish()
        dest=self.home/"public_html"/"b2b"
        raw=b"FOREIGN CONTENT"
        (dest/"index.html").write_bytes(raw)
        marker=dest/".zomorod-b2b-release.json"
        metadata=json.loads(marker.read_text())
        metadata["files"]["b2b/index.html"]={"size":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}
        marker.write_text(json.dumps(metadata))
        with self.assertRaisesRegex(RuntimeError,"independently reviewed source"):
            rollback_verified(self.home,SOURCE,RUN,
                owner_authorization=f"owner-rollback-b2b:{SOURCE}:{RUN}",
                require_owner=False)
        self.assertEqual((dest/"index.html").read_bytes(),raw)

    @unittest.skipUnless(os.name=="posix","Unix directory mode required")
    def test_group_writable_document_root_refuses_release(self):
        docroot=self.home/"public_html"
        docroot.chmod(0o775)
        with self.assertRaises(RuntimeError):
            preflight(self.home,False)
        self.assertFalse((docroot/"b2b").exists())

    @unittest.skipUnless(os.name=="posix","atomic renameat2 requires Linux")
    def test_no_cross_release_replay(self):
        self.publish()
        with self.assertRaises(PermissionError):
            rollback_verified(self.home,SOURCE,"44249493819",
                owner_authorization=f"owner-rollback-b2b:{SOURCE}:{RUN}",
                require_owner=False)

if __name__=="__main__":
    unittest.main()
