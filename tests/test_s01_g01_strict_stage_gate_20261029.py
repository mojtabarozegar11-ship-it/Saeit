"""Synthetic offline acceptance tests; no live site, payment or private artifact."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/s01_g01_strict_stage_gate_20261029.py"
spec = importlib.util.spec_from_file_location("s01_g01_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class StageGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "synthetic.zip"
        self.files = {name: (name + " synthetic").encode() for name in gate.REQUIRED}
        self.files["moj1-commerce-policy.mjs"] = (
            b"export const MOJ1_COMMERCE = Object.freeze({"
            b"ownerApproved:false, checkoutEnabled:false, verifiedBackend:false,"
            b"contractAddress:null});"
        )

    def build(self, *, omit_manifest_name=None, policy=None, extra=None):
        files = dict(self.files)
        if policy is not None:
            files["moj1-commerce-policy.mjs"] = policy
        if extra:
            files.update(extra)
        manifest_files = {
            name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in files.items() if name != omit_manifest_name
        }
        with zipfile.ZipFile(self.path, "w") as z:
            for name, data in files.items():
                z.writestr("ramadan-war/" + name, data)
            z.writestr("ramadan-war/preview-manifest.json", json.dumps({
                "version": "G01-R24", "files": manifest_files
            }))

    def test_valid_complete_manifest_is_review_only(self):
        self.build()
        result = gate.verify(self.path)
        self.assertEqual(result["status"], "READY_FOR_REVIEW")
        self.assertFalse(result["deploy_authorized"])
        self.assertFalse(result["live_verified"])

    def test_manifest_must_cover_every_runtime_asset(self):
        self.build(omit_manifest_name="game.js")
        with self.assertRaisesRegex(ValueError, "MANIFEST_COVERAGE_MISMATCH"):
            gate.verify(self.path)

    def test_payment_policy_flags_must_be_disabled(self):
        self.build(policy=b"MOJ1 ownerApproved:true checkoutEnabled:false verifiedBackend:false contractAddress:null")
        with self.assertRaisesRegex(ValueError, "MOJ1_DISABLED"):
            gate.verify(self.path)

    def test_unsafe_archive_path_rejected(self):
        self.build(extra={"../private.txt": b"not safe"})
        with self.assertRaisesRegex(ValueError, "UNSAFE_ARCHIVE_MEMBER"):
            gate.verify(self.path)

    def test_case_insensitive_member_alias_is_rejected(self):
        self.build(extra={"GAME.js": b"alias"})
        with self.assertRaisesRegex(ValueError, "CASEFOLD_MEMBER_COLLISION"):
            gate.verify(self.path)

    def test_explicit_dot_segment_alias_is_rejected(self):
        self.build()
        with zipfile.ZipFile(self.path, "a") as archive:
            archive.writestr("ramadan-war/./game.js", b"alias")
        with self.assertRaisesRegex(ValueError, "UNSAFE_ARCHIVE_MEMBER"):
            gate.verify(self.path)


if __name__ == "__main__":
    unittest.main()
