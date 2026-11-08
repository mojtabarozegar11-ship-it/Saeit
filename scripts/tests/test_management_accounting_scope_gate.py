"""No arbitrary path or release claim can pass the source-only manifest gate."""
import pathlib
import hashlib
import tempfile
import unittest

from deploy.management_accounting_scope_gate import SCHEMA, RUNTIME_FILES, audit_scope, git_blob_sha1


class ManagementAccountingScopeGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.files = []
        for relative in RUNTIME_FILES:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            payload = relative.encode("utf-8")
            target.write_bytes(payload)
            self.files.append({"path": relative, "git_blob_sha1": git_blob_sha1(payload), "sha256": hashlib.sha256(payload).hexdigest()})
        self.manifest = {
            "schema": SCHEMA,
            "production_release_permitted": False,
            "runtime_files": self.files,
        }

    def test_exact_seven_file_source_scope_passes_without_release(self):
        result = audit_scope(self.root, self.manifest)
        self.assertTrue(result["source_scope_verified"])
        self.assertFalse(result["production_release_permitted"])
        self.assertFalse(result["backup_restore_attested"])

    def test_changed_accounting_service_fails_closed(self):
        (self.root / "accounting/services.py").write_text("tampered", encoding="utf-8")
        self.assertIn("content_hash_mismatch:accounting/services.py", audit_scope(self.root, self.manifest)["issues"])

    def test_unrelated_public_html_file_is_denied(self):
        self.manifest["runtime_files"][0]["path"] = "public_html/faremah/index.html"
        self.assertFalse(audit_scope(self.root, self.manifest)["source_scope_verified"])

    def test_release_flag_cannot_be_enabled(self):
        self.manifest["production_release_permitted"] = True
        self.assertIn("release_flag_must_be_false", audit_scope(self.root, self.manifest)["issues"])

    def test_incorrect_sha256_is_denied_even_if_git_hash_matches(self):
        self.manifest["runtime_files"][0]["sha256"] = "0" * 64
        self.assertIn("content_sha256_mismatch:accounting/admin.py", audit_scope(self.root, self.manifest)["issues"])

    def test_duplicate_path_is_denied(self):
        self.manifest["runtime_files"][1] = dict(self.manifest["runtime_files"][0])
        self.assertIn("duplicate_runtime_path", audit_scope(self.root, self.manifest)["issues"])

    def test_symlink_in_source_path_is_denied(self):
        target = self.root / "accounting/services.py"
        target.unlink()
        target.symlink_to(self.root / "accounting/admin.py")
        self.assertIn("symlink_not_allowed:accounting/services.py", audit_scope(self.root, self.manifest)["issues"])


if __name__ == "__main__":
    unittest.main()
