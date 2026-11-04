#!/usr/bin/env python3
"""Read-only release gate for an R58 private ZIP or standalone preview.

Checks both package-wide and embedded runtime manifests. An optional GitHub
contents index (a JSON array of name/sha/type entries) detects drift between
an independently built distribution and its designated development branch.
No network, extraction, deployment, or modification of the candidate occurs.
"""
import argparse
import hashlib
import json
import pathlib
import stat
import zipfile

# The repository intentionally contains a truncated development copy. A
# release may replace it only with the exact complete CC-BY model pinned by
# fetch_verified_models.sh; arbitrary binary drift is never accepted.
PINNED_FULL_MODEL_BLOBS = {
    "soldier-rigged-ccby.glb": "b00ed33108f2579880c82cd27d10f9237ff3a219"
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git_blob(data):
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def inspect(candidate, source_index=None):
    errors = []
    checks = {}
    diffs = []
    rehydrated = []
    with zipfile.ZipFile(candidate) as archive:
        members = archive.infolist()
        names = [entry.filename for entry in members]
        safe = len(members) <= 1000 and len(names) == len(set(names))
        safe = safe and sum(entry.file_size for entry in members) <= 100_000_000
        for entry in members:
            path = pathlib.PurePosixPath(entry.filename)
            if (path.is_absolute() or not path.parts or any(p in (".", "..") for p in path.parts)
                    or "\\" in entry.filename or any(ord(c) < 32 for c in entry.filename)
                    or stat.S_IFMT(entry.external_attr >> 16) == stat.S_IFLNK):
                safe = False
        if len({name.casefold() for name in names}) != len(names):
            safe = False
        checks["safe_zip_paths_and_size"] = safe
        if not safe:
            errors.append("unsafe_or_ambiguous_archive_members")
            return {"status": "BLOCKED", "checks": checks, "errors": errors,
                    "source_mismatches": diffs, "public_release_authorized": False}
        bad = archive.testzip()
        checks["zip_crc"] = bad is None
        if bad:
            errors.append("zip_crc:" + bad)
        present = set(names)
        if "PACKAGE-MANIFEST.json" in present:
            package = json.loads(archive.read("PACKAGE-MANIFEST.json"))
            outer = package.get("files", {})
            expected = present - {"PACKAGE-MANIFEST.json", "PACKAGE-FILELIST.txt"}
            checks["package_file_coverage"] = set(outer) == expected
            if not checks["package_file_coverage"]:
                errors.append("package_manifest_member_coverage")
            outer_bad = []
            for name, record in outer.items():
                if name not in present:
                    outer_bad.append(name)
                    continue
                data = archive.read(name)
                if len(data) != record.get("bytes") or digest(data) != record.get("sha256"):
                    outer_bad.append(name)
            checks["package_sha256"] = not outer_bad
            errors.extend("package_sha256:" + name for name in outer_bad)
            runtime = sorted(name for name in outer if name.startswith("ramadan-war/"))
            canonical = "\n".join(
                f"{name}\t{outer[name]['bytes']}\t{outer[name]['sha256']}"
                for name in runtime
            ).encode("utf-8")
            checks["runtime_manifest_digest"] = digest(canonical) == package.get("runtime_manifest_sha256")
            if not checks["runtime_manifest_digest"]:
                errors.append("runtime_manifest_digest")
        else:
            checks["package_file_coverage"] = None
            checks["package_sha256"] = None
            checks["runtime_manifest_digest"] = None

        preview_path = "ramadan-war/preview-manifest.json"
        if preview_path not in present:
            errors.append("missing_preview_manifest")
            checks["preview_sha256"] = False
        else:
            preview = json.loads(archive.read(preview_path))
            checks["payments_disabled"] = preview.get("payment_status") == "disabled"
            if not checks["payments_disabled"]:
                errors.append("payments_not_confirmed_disabled")
            bad_entries = []
            for name, record in preview.get("files", {}).items():
                member = "ramadan-war/" + name
                if member not in present:
                    bad_entries.append(name)
                    continue
                data = archive.read(member)
                if len(data) != record.get("bytes") or digest(data) != record.get("sha256"):
                    bad_entries.append(name)
            checks["preview_sha256"] = not bad_entries and bool(preview.get("files"))
            errors.extend("preview_sha256:" + name for name in bad_entries)

        if source_index is not None:
            refs = (entry for entry in source_index if entry.get("type") == "file")
            compared = 0
            for entry in refs:
                name = "ramadan-war/" + entry["name"]
                if name not in present:
                    continue  # The repo also contains tests and unreleased tools.
                compared += 1
                blob = git_blob(archive.read(name))
                if blob != entry.get("sha"):
                    if blob == PINNED_FULL_MODEL_BLOBS.get(entry["name"]):
                        rehydrated.append(entry["name"])
                    else:
                        diffs.append(entry["name"])
            checks["source_branch_parity"] = not diffs and compared > 0
            checks["source_files_compared"] = compared
            checks["pinned_model_rehydrations"] = rehydrated
            errors.extend("source_mismatch:" + name for name in diffs)
        else:
            checks["source_branch_parity"] = None

    return {"status": "READY_FOR_INDEPENDENT_REVIEW" if not errors else "BLOCKED",
            "checks": checks, "errors": errors,
            "source_mismatches": diffs, "public_release_authorized": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip_file", type=pathlib.Path)
    parser.add_argument("--source-index", type=pathlib.Path,
                        help="optional GitHub contents JSON for this release branch")
    args = parser.parse_args()
    try:
        source = json.loads(args.source_index.read_text("utf-8")) if args.source_index else None
        result = inspect(args.zip_file, source)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        result = {"status": "BLOCKED", "errors": ["audit_error:" + str(exc)],
                  "public_release_authorized": False}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "READY_FOR_INDEPENDENT_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
