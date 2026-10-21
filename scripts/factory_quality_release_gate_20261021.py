#!/usr/bin/env python3
"""Fail-closed offline product release gate. No publication or financial action."""
import argparse, hashlib, json, pathlib, sys, zipfile

ROLES = ("scientific", "technical", "legal", "independent_human")
def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()

def check(manifest):
    errors = []
    product = manifest.get("product", {})
    if not product.get("family") or not product.get("version"):
        errors.append("missing family/version")
    for key in ("source", "artifact"):
        item = manifest.get(key, {})
        path = pathlib.Path(item.get("path", ""))
        if not path.is_file() or not item.get("sha256"):
            errors.append(key + ": missing file or digest")
        elif sha(path) != item["sha256"]:
            errors.append(key + ": SHA256 mismatch")
    artifact = pathlib.Path(manifest.get("artifact", {}).get("path", ""))
    if artifact.is_file():
        if not zipfile.is_zipfile(artifact):
            errors.append("artifact: not a ZIP")
        else:
            with zipfile.ZipFile(artifact) as z:
                if not z.namelist() or z.testzip() is not None:
                    errors.append("artifact: empty or CRC failure")
                for name in z.namelist():
                    p = pathlib.PurePosixPath(name)
                    if p.is_absolute() or ".." in p.parts:
                        errors.append("artifact: unsafe ZIP member")
    criteria = manifest.get("criteria", [])
    if len(criteria) != 100 or len({c.get("id") for c in criteria if isinstance(c, dict)}) != 100:
        errors.append("criteria: require 100 distinct criteria")
    else:
        for c in criteria:
            if not isinstance(c, dict) or not isinstance(c.get("score"), int) or isinstance(c.get("score"), bool) or not 0 <= c["score"] <= 10 or not c.get("evidence_sha256"):
                errors.append("criteria: missing scored evidence")
                break
    for name in ("cli_tests", "invalid_tests", "independent_oracle", "rework_retest", "backup_restore_test", "live_delivery_test"):
        if manifest.get(name, {}).get("passed") is not True or not manifest.get(name, {}).get("evidence_sha256"):
            errors.append(name + ": missing verified evidence")
    for role in ROLES:
        approval = manifest.get("approvals", {}).get(role, {})
        if approval.get("verified") is not True or not approval.get("receipt_sha256"):
            errors.append(role + ": unverified approval")
    if manifest.get("owner_publication_permission") is not True:
        errors.append("owner publication permission absent")
    if manifest.get("rights_cleared") is not True:
        errors.append("rights not cleared")
    if len(criteria) == 100 and sum(c.get("score", 0) for c in criteria if isinstance(c, dict)) != 1000:
        errors.append("quality score below 1000")
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
