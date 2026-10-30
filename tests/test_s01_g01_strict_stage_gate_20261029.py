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
                "version": "G01-R26", "files": manifest_files
            }))

    def test_valid_complete_manifest_is_review_only(self):
        self.build()
        result = gate.verify(self.path)
        self.assertEqual(result["status"], "READY_FOR_REVIEW")
        self.assertFalse(result["deploy_authorized"])
        self.assertFalse(result["live_verified"])

    def test_r26_navigation_runtime_is_mandatory_even_with_valid_manifest(self):
        self.files.pop("objective-navigation.mjs")
        self.build()
        with self.assertRaisesRegex(ValueError, "MISSING_REQUIRED_RUNTIME"):
            gate.verify(self.path)

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

    def test_unicode_normalization_alias_is_rejected(self):
        self.build(extra={"game\u0301.js": b"decomposed", "gam\u00e9.js": b"composed"})
        with self.assertRaisesRegex(ValueError, "NORMALIZED_MEMBER_COLLISION"):
            gate.verify(self.path)

    def test_duplicate_manifest_json_key_is_rejected(self):
        self.build()
        with zipfile.ZipFile(self.path, "r") as archive:
            files = {entry.filename: archive.read(entry.filename)
                     for entry in archive.infolist()
                     if entry.filename != "ramadan-war/preview-manifest.json"}
            original = archive.read("ramadan-war/preview-manifest.json").decode("utf-8")
        duplicate = original.replace('"version": "G01-R26",',
                                     '"version": "G01-R26", "version": "G01-R999",', 1)
        with zipfile.ZipFile(self.path, "w") as archive:
            for name, data in files.items():
                archive.writestr(name, data)
            archive.writestr("ramadan-war/preview-manifest.json", duplicate)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_MANIFEST_KEY"):
            gate.verify(self.path)

    def test_archive_size_limit_fails_before_zip_processing(self):
        from unittest.mock import patch
        self.build()
        with patch.object(gate, "MAX_ARCHIVE_BYTES", 100):
            with self.assertRaisesRegex(ValueError, "UNSAFE_OR_OVERSIZED_ARCHIVE"):
                gate.verify(self.path)

    def test_manifest_size_limit_blocks_untrusted_json_expansion(self):
        from unittest.mock import patch
        self.build()
        with patch.object(gate, "MAX_MANIFEST_BYTES", 10):
            with self.assertRaisesRegex(ValueError, "OVERSIZED_MANIFEST"):
                gate.verify(self.path)

    def test_nonportable_compression_is_rejected_before_release(self):
        self.build()
        with zipfile.ZipFile(self.path, "a") as archive:
            archive.writestr("ramadan-war/unsupported-compression.bin", b"test",
                             compress_type=zipfile.ZIP_BZIP2)
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_ZIP_COMPRESSION"):
            gate.verify(self.path)

    def test_explicit_dot_segment_alias_is_rejected(self):
        self.build()
        with zipfile.ZipFile(self.path, "a") as archive:
            archive.writestr("ramadan-war/./game.js", b"alias")
        with self.assertRaisesRegex(ValueError, "UNSAFE_ARCHIVE_MEMBER"):
            gate.verify(self.path)

    def test_file_directory_member_collision_rejected(self):
        self.build(extra={"game.js/child.txt": b"conflicting path"})
        with self.assertRaisesRegex(ValueError, "FILE_DIRECTORY_MEMBER_COLLISION"):
            gate.verify(self.path)

    def test_unix_device_member_rejected(self):
        import stat
        self.build()
        special = zipfile.ZipInfo("ramadan-war/device")
        special.create_system = 3
        special.external_attr = (stat.S_IFCHR | 0o600) << 16
        with zipfile.ZipFile(self.path, "a") as archive:
            archive.writestr(special, b"device")
        with self.assertRaisesRegex(ValueError, "UNSAFE_ARCHIVE_MEMBER_TYPE"):
            gate.verify(self.path)

    def test_extreme_compression_ratio_rejected(self):
        self.build()
        with zipfile.ZipFile(self.path, "a") as archive:
            archive.writestr("ramadan-war/bomb.txt", b"0" * 6_000_000,
                             compress_type=zipfile.ZIP_DEFLATED)
        with self.assertRaisesRegex(ValueError, "SUSPICIOUS_COMPRESSION_RATIO"):
            gate.verify(self.path)


    def test_duplicate_disabled_flag_with_true_override_is_rejected(self):
        self.build(policy=(
            b"export const MOJ1_COMMERCE = Object.freeze({"
            b"ownerApproved:false, ownerApproved:true,"
            b"checkoutEnabled:false, verifiedBackend:false, contractAddress:null});"
        ))
        with self.assertRaisesRegex(ValueError, "MOJ1_DISABLED_SOURCE_FLAGS_MISSING"):
            gate.verify(self.path)

    def test_duplicate_contract_address_with_live_override_is_rejected(self):
        self.build(policy=(
            b"export const MOJ1_COMMERCE = Object.freeze({"
            b"ownerApproved:false, checkoutEnabled:false, verifiedBackend:false,"
            b"contractAddress:null, contractAddress:liveAddress});"
        ))
        with self.assertRaisesRegex(ValueError, "MOJ1_CONTRACT_MUST_BE_NULL"):
            gate.verify(self.path)

    def test_nonliteral_dynamic_checkout_flag_is_rejected(self):
        self.build(policy=(
            b"export const MOJ1_COMMERCE = Object.freeze({"
            b"ownerApproved:false, checkoutEnabled:enablePayments,"
            b"verifiedBackend:false, contractAddress:null});"
        ))
        with self.assertRaisesRegex(ValueError, "MOJ1_DISABLED_SOURCE_FLAGS_MISSING"):
            gate.verify(self.path)


if __name__ == "__main__":
    unittest.main()
