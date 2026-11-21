#!/usr/bin/env python3
"""Fail-closed offline product release gate. No publication or financial action."""
import argparse, hashlib, hmac, json, pathlib, re, stat, sys, zipfile

ROLES = ("scientific", "technical", "legal", "independent_human")
HEX256 = re.compile(r"^[0-9a-f]{64}$")
def valid_receipt(record, product):
    """Verify an exact version-bound SHA-256 digest of an external receipt file.
    Digest alone is not proof of an authentic human signature or independent review.
    """
    if not isinstance(record, dict) or record.get("verified") is not True:
        return False
    raw_path = record.get("receipt_path", "")
    if not isinstance(raw_path, str) or not raw_path:
        return False
    path = pathlib.Path(raw_path)
    expected = record.get("receipt_sha256", "")
    if not isinstance(expected, str) or not HEX256.fullmatch(expected) or not path.is_file() or path.is_symlink():
        return False
    if not hmac.compare_digest(sha(path), expected):
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return False
    return payload.get("family") == product.get("family") and payload.get("version") == product.get("version") and payload.get("role") == record.get("role")

def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()

def signed_release_clearance(manifest, artifact_path):
    """Delegate commercial approval to the existing Ed25519 four-role verifier.

    The candidate JSON alone never grants authority. Without an externally
    pinned trust root and authentic signatures, this returns False.
    """
    config = manifest.get("signed_release", {})
    if not isinstance(config, dict):
        return False
    paths = {}
    for field in ("decision", "gate_report", "catalog", "trusted_reviewers"):
        raw = config.get(field)
        if not isinstance(raw, str) or not raw:
            return False
        path = pathlib.Path(raw)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
            return False
        paths[field] = path
    verifier_path = pathlib.Path(__file__).resolve().with_name("factory_quality_signed_approval_v1.py")
    if verifier_path.is_symlink() or not verifier_path.is_file():
        return False
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("factory_signed_quality_verifier", str(verifier_path))
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)
        data = {key: json.loads(path.read_text(encoding="utf-8")) for key, path in paths.items()}
        verdict = verifier.inspect_approval(
            data["decision"], data["gate_report"], str(artifact_path),
            str(paths["catalog"]), data["trusted_reviewers"])
        return (verdict.get("eligible") is True
                and hmac.compare_digest(verdict.get("artifact_sha256", ""), sha(artifact_path))
                and verdict.get("verifiable_reviewer_count", 0) >= 4)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError, UnicodeError):
        return False


def check(manifest):
    errors = []
    if not isinstance(manifest, dict):
        return ["manifest: JSON object required"]
    product = manifest.get("product", {})
    if not isinstance(product, dict):
        product = {}
    if not product.get("family") or not product.get("version"):
        errors.append("missing family/version")
    for key in ("source", "artifact"):
        item = manifest.get(key, {})
        item = item if isinstance(item, dict) else {}
        candidate = item.get("path", "")
        path = pathlib.Path(candidate) if isinstance(candidate, str) and candidate else pathlib.Path("/")
        if path.is_symlink():
            errors.append(key + ": unsafe symlink")
        elif not path.is_file() or not item.get("sha256"):
            errors.append(key + ": missing file or digest")
        elif sha(path) != item["sha256"]:
            errors.append(key + ": SHA256 mismatch")
    artifact_item = manifest.get("artifact", {})
    artifact_item = artifact_item if isinstance(artifact_item, dict) else {}
    artifact_name = artifact_item.get("path")
    artifact = pathlib.Path(artifact_name) if isinstance(artifact_name, str) and artifact_name else pathlib.Path("/")
    if artifact.is_symlink():
        errors.append("artifact: unsafe symlink")
    elif artifact.is_file():
        try:
            if not 0 < artifact.stat().st_size <= 64 * 1024 * 1024:
                errors.append("artifact: archive exceeds limit")
            elif not zipfile.is_zipfile(artifact):
                errors.append("artifact: not a ZIP")
            else:
                with zipfile.ZipFile(artifact) as z:
                    members = z.infolist()
                    names = set()
                    total = 0
                    if not 1 <= len(members) <= 2500:
                        errors.append("artifact: invalid member count")
                    for item in members:
                        name = item.filename
                        p = pathlib.PurePosixPath(name)
                        total += item.file_size
                        if (not name or name in names or name.startswith("/")
                                or chr(92) in name or p.is_absolute() or ".." in p.parts
                                or item.file_size > 40 * 1024 * 1024
                                or total > 150 * 1024 * 1024
                                or stat.S_ISLNK(item.external_attr >> 16)):
                            errors.append("artifact: unsafe ZIP member")
                            break
                        names.add(name)
                    if not any(e.startswith("artifact:") for e in errors):
                        if z.testzip() is not None:
                            errors.append("artifact: CRC failure")
        except (OSError, ValueError, RuntimeError, EOFError, zipfile.BadZipFile):
            errors.append("artifact: unreadable ZIP")
    criteria = manifest.get("criteria", [])
    if not isinstance(criteria, list) or len(criteria) != 100 or len({c.get("id") for c in criteria if isinstance(c, dict)}) != 100:
        errors.append("criteria: require 100 distinct criteria")
    else:
        for c in criteria:
            if not isinstance(c, dict) or not isinstance(c.get("score"), int) or isinstance(c.get("score"), bool) or not 0 <= c["score"] <= 10 or not isinstance(c.get("evidence_sha256"), str) or not HEX256.fullmatch(c["evidence_sha256"]):
                errors.append("criteria: missing scored evidence")
                break
    for name in ("cli_tests", "invalid_tests", "independent_oracle", "rework_retest", "backup_restore_test", "live_delivery_test"):
        evidence = manifest.get(name, {})
        evidence = evidence if isinstance(evidence, dict) else {}
        digest = evidence.get("evidence_sha256")
        if evidence.get("passed") is not True or not isinstance(digest, str) or not HEX256.fullmatch(digest):
            errors.append(name + ": missing verified evidence")
    for role in ROLES:
        approvals = manifest.get("approvals", {})
        approvals = approvals if isinstance(approvals, dict) else {}
        approval = approvals.get(role, {})
        approval = approval if isinstance(approval, dict) else {}
        if not valid_receipt(dict(approval, role=role), product):
            errors.append(role + ": unverified approval")
    # A digest-bound receipt does not establish legal authority or authentic signature.
    # Require an explicit separately attested independent identity check.
    if manifest.get("independent_identity_verification") is not True:
        errors.append("independent identity verification absent")
    if manifest.get("owner_publication_permission") is not True:
        errors.append("owner publication permission absent")
    if manifest.get("rights_cleared") is not True:
        errors.append("rights not cleared")
    if isinstance(criteria, list) and len(criteria) == 100 and sum(c.get("score", 0) for c in criteria if isinstance(c, dict) and type(c.get("score")) is int) != 1000:
        errors.append("quality score below 1000")
    if not signed_release_clearance(manifest, artifact):
        errors.append("authenticated signed four-party clearance absent")
    return errors

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    args = parser.parse_args()
    manifest = json.loads(pathlib.Path(args.manifest).read_text(encoding="utf-8"))
    errors = check(manifest)
    print(json.dumps({"release_allowed": not errors, "blockers": errors}, ensure_ascii=False))
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
