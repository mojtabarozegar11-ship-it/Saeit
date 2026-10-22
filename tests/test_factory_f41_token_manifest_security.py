"""Regression: ALL F41 token manifest fields are bound to source and fail closed."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import factory_f41_token_builder_v2 as token


class TokenReceiptTests(unittest.TestCase):
    def test_every_claim_is_verified_not_just_hashes(self):
        spec = ROOT / "factory_config" / "f41_pilot_token.json"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for key, mutated in [
                ("name", "Other Name"),
                ("symbol", "OTHER"),
                ("network", "mainnet"),
                ("token_supply", "999"),
                ("verified_generation", 100),
                ("independent_audit", True),
                ("site_writes", 1),
                ("quality_1000_certified", True),
                ("production_deployment_enabled", True)
            ]:
                with self.subTest(key=key):
                    target = root / "pilot"
                    # New output after removing only our own temporary-test candidate.
                    token.build(spec, target)
                    manifest_path = target / "manifest.json"
                    item = json.loads(manifest_path.read_text())
                    item[key] = mutated
                    manifest_path.write_text(json.dumps(item))
                    with self.assertRaisesRegex(ValueError, "F41_RECEIPT_MISMATCH"):
                        token.verify(spec, target)
                    # TemporaryDirectory owns the path, so clean up exact test files only.
                    for file in target.rglob("*"):
                        if file.is_file():
                            file.unlink()
                    for folder in sorted((p for p in target.rglob("*") if p.is_dir()), reverse=True):
                        folder.rmdir()
                    target.rmdir()


if __name__ == "__main__":
    unittest.main()
