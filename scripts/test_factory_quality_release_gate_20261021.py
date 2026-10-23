#!/usr/bin/env python3
"""Offline negative regression tests: never authorize commercial release from unverified manifests."""
import hashlib
import importlib.util
import pathlib
import tempfile
import zipfile
import stat

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
        # Even a digest-correct receipt for the wrong version must be rejected.
        receipt = root / "legal-receipt.json"
        receipt.write_text('{"family":"F28","version":"wrong-version","role":"legal"}', encoding="utf-8")
        manifest["approvals"]["legal"]["receipt_path"] = str(receipt)
        manifest["approvals"]["legal"]["receipt_sha256"] = digest(receipt)
        assert any("legal" in e for e in gate.check(manifest))
        receipt.write_text('{"family":"F28","version":"test-only","role":"legal"}', encoding="utf-8")
        assert any("legal" in e for e in gate.check(manifest)), "Stale receipt digest must fail"
        manifest["approvals"]["legal"]["receipt_sha256"] = digest(receipt)
        assert gate.valid_receipt(dict(manifest["approvals"]["legal"], role="legal"), manifest["product"])
        assert not gate.valid_receipt(dict(manifest["approvals"]["legal"], role="scientific"), manifest["product"])

        manifest["owner_publication_permission"] = True
        manifest["rights_cleared"] = True
        # Even complete self-declared 1000/1000 evidence cannot bypass signatures.
        assert any("authenticated signed four-party clearance absent" in e
                   for e in gate.check(manifest))
        # Path traversal and ZIP symlink must be rejected with matching archive hash.
        with zipfile.ZipFile(artifact, "w") as z:
            z.writestr("../escape.txt", "malicious")
        manifest["artifact"]["sha256"] = digest(artifact)
        assert any("unsafe ZIP member" in e for e in gate.check(manifest))
        with zipfile.ZipFile(artifact, "w") as z:
            symlink = zipfile.ZipInfo("source-link")
            symlink.create_system = 3
            symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(symlink, "target")
        manifest["artifact"]["sha256"] = digest(artifact)
        assert any("unsafe ZIP member" in e for e in gate.check(manifest))
        with zipfile.ZipFile(artifact, "w") as z:
            z.writestr("folder\\\\payload.py", "malicious")
        manifest["artifact"]["sha256"] = digest(artifact)
        assert any("unsafe ZIP member" in e for e in gate.check(manifest))
        # Changed source bytes invalidate the exact immutable product identity.
        source.write_text("print('changed')\\n", encoding="utf-8")
        assert any("source: SHA256 mismatch" in e for e in gate.check(manifest))
        # Evidence strings are NOT authentic signatures. Current gate is insufficient.
        # Until cryptographic receipt verification is integrated, deployment must remain blocked.
        print("NEGATIVE_REGRESSION_PASS; CRYPTOGRAPHIC_RECEIPT_VERIFICATION_NOT_IMPLEMENTED")

if __name__ == "__main__":
    main()
