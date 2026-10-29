"""Offline S-01 cross-cycle integrity checks; no network, payments or deploy."""
import hashlib
import importlib.util
import io
import json
import unittest
from pathlib import Path
from zipfile import ZipFile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/s01_g01_preview_artifact_gate.py"
spec = importlib.util.spec_from_file_location("s01_g01_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

REV = "a" * 40
GAME = b"export const safeGame = true;\n"


def fixture(*, altered=False, enabled=False, traversal=False):
    files = {
        "game.js": GAME,
        "index.html": b"<html><title>Preview</title></html>",
        "engine3d.js": b"export const engine = true;\n",
        "THREE-LICENSE.txt": b"test license",
        "ASSET-CREDITS.md": b"test attribution",
        "moj1-commerce-policy.mjs": (
            b"checkoutEnabled:false ownerApproved:false "
            b"verifiedBackend:false contractAddress:null"
        ),
    }
    files.update({f"dummy-{i:02d}.txt": b"sample" for i in range(21)})
    if traversal:
        files["../escape.txt"] = b"escape"
    manifest = {
        "format": "ramadan-war-offline-preview-v1",
        "source_revision": REV,
        "payment_status": "enabled" if enabled else "disabled",
        "files": {
            name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in files.items()
        },
    }
    if altered:
        files["game.js"] = b"tampered"
    inner_buffer = io.BytesIO()
    with ZipFile(inner_buffer, "w") as inner:
        for name, data in files.items():
            inner.writestr("ramadan-war/" + name, data)
        inner.writestr("ramadan-war/preview-manifest.json", json.dumps(manifest))
        inner.writestr("ramadan-war/PLAY-README.txt", "Revision: " + REV)
    outer_buffer = io.BytesIO()
    with ZipFile(outer_buffer, "w") as outer:
        outer.writestr("ramadan-war-preview.zip", inner_buffer.getvalue())
    return outer_buffer.getvalue()


class ArtifactGateTests(unittest.TestCase):
    def test_valid_preview_passes_as_internal_only(self):
        result = gate.verify(fixture(), REV, gate.git_blob(GAME))
        self.assertEqual(result["result"], "PASS_INTERNAL_PREVIEW_ONLY")
        self.assertFalse(result["live_deployed"])
        self.assertFalse(result["payment_enabled"])

    def test_modified_payload_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "manifest digest/length mismatch"):
            gate.verify(fixture(altered=True), REV, gate.git_blob(GAME))

    def test_payment_enabled_manifest_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "payment status mismatch"):
            gate.verify(fixture(enabled=True), REV, gate.git_blob(GAME))

    def test_unreviewed_game_blob_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "differs from reviewed"):
            gate.verify(fixture(), REV, "b" * 40)

    def test_traversal_asset_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsafe archive entry"):
            gate.verify(fixture(traversal=True), REV, gate.git_blob(GAME))


if __name__ == "__main__":
    unittest.main()
