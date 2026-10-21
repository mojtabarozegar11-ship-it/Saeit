#!/usr/bin/env python3
"""Offline negative regression tests: never authorize commercial release from unverified manifests."""
import hashlib
import importlib.util
import pathlib
import tempfile
import zipfile

gate_path = pathlib.Path(__file__).with_name("factory_quality_release_gate_20261021.py")
spec = importlib.util.spec_from_file_location("factory_quality_gate", gate_path)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        source = root / "source.py"
        source.write_text("print('ok')\n", encoding="utf-8")
        artifact = root / "product.zip"
        with zipfile.ZipFile(artifact, "w") as z:
            z.write(source, "source.py")
        manifest = {
            "product": {"family": "F28", "version": "test-only"},
            "source": {"path": str(source), "sha256": digest(source)},
            "artifact": {"path": str(artifact), "sha256": digest(artifact)},
            "criteria": [{"id": f"Q{i:03d}", "score": 10, "evidence_sha256": "unverified"} for i in range(1, 101)],
            "approvals": {role: {"verified": True, "receipt_sha256": "unverified"} for role in gate.ROLES},
            "owner_publication_permission": False,
            "rights_cleared": False,
        }
        assert gate.check(manifest), "Incomplete evidence must block release"
        manifest["artifact"]["sha256"] = "0" * 64
        assert any("SHA256 mismatch" in e for e in gate.check(manifest))
        manifest["artifact"]["sha256"] = digest(artifact)
        manifest["criteria"] = manifest["criteria"][:-1]
        assert any("100 distinct" in e for e in gate.check(manifest))
        manifest["criteria"] = [{"id": f"Q{i:03d}", "score": 10, "evidence_sha256": "unverified"} for i in range(1, 101)]
        manifest["approvals"]["legal"] = {"verified": False, "receipt_sha256": "unverified"}
        assert any("legal" in e for e in gate.check(manifest))
        manifest["approvals"]["legal"]["verified"] = True
        manifest["owner_publication_permission"] = True
        manifest["rights_cleared"] = True
        # Evidence strings are NOT authentic signatures. Current gate is insufficient.
        # Until cryptographic receipt verification is integrated, deployment must remain blocked.
        print("NEGATIVE_REGRESSION_PASS; CRYPTOGRAPHIC_RECEIPT_VERIFICATION_NOT_IMPLEMENTED")

if __name__ == "__main__":
    main()
