#!/usr/bin/env python3
"""Fail-closed evaluator for version-bound factory evidence supplier dossiers.

It validates machine-measurable claims against the exact product bytes and
produces a review worklist. It never assigns professional points, authenticates
people, or authorizes release.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import zipfile

SCHEMA = "saeit.factory.quality-evidence-evaluation.v1"
SUPPLIER_SCHEMA = "saeit.factory.quality-evidence-supply.v1"
CATALOG_SCHEMA = "saeit.factory.quality-100-groups.v2"
HEX = re.compile(r"^[a-f0-9]{64}$")
PRODUCT = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
MAX_JSON = 500_000
MAX_PACKAGE = 25 * 1024 * 1024
MAX_MEMBERS = 100
MAX_UNPACKED = 40 * 1024 * 1024
F28_RECIPE = "greenhouse_crop_margin"
F28_SOURCE = "c446aeaa32494c93a453f524390ee14061d6f36da3228b3d4b15c5b794d2bc1e"
F28_ARTIFACT = "7ba2168c90617b236d10ee4542ec9fd276f3f524809ddd001f18f5a5634fc553"
F28_CRITERIA = ("Q036", "Q057", "Q061", "Q064", "Q069")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(ok, code):
    if not ok:
        raise ValueError(code)


def read_json(path):
    p = Path(path)
    require(p.is_file() and not p.is_symlink() and 0 < p.stat().st_size <= MAX_JSON,
            "EVALUATOR_JSON_UNSAFE")
    value = json.loads(p.read_text(encoding="utf8"))
    require(isinstance(value, dict), "EVALUATOR_JSON_INVALID")
    return value


def load_catalog(path):
    data = read_json(path)
    groups = data.get("groups")
    ids = ["Q%03d" % n for n in range(1, 101)]
    require(data.get("schema") == CATALOG_SCHEMA and data.get("group_count") == 100
            and data.get("points_per_group") == 10 and data.get("total_points") == 1000
            and isinstance(groups, dict) and list(groups) == ids,
            "EVALUATOR_CATALOG_CONTRACT_INVALID")
    require(all(isinstance(row, dict) and isinstance(row.get("name"), str)
                for row in groups.values()), "EVALUATOR_CATALOG_ROW_INVALID")
    return groups


def inspect_zip(path, recipe):
    package = Path(path)
    require(package.is_file() and not package.is_symlink()
            and 0 < package.stat().st_size <= MAX_PACKAGE, "EVALUATOR_PACKAGE_UNSAFE")
    members = []
    seen = set()
    total = 0
    try:
        with zipfile.ZipFile(str(package)) as archive:
            entries = archive.infolist()
            require(0 < len(entries) <= MAX_MEMBERS and archive.testzip() is None,
                    "EVALUATOR_ZIP_CRC_FAILED")
            for item in entries:
                name = item.filename
                parts = name.split("/")
                mode = (item.external_attr >> 16) & 0o170000
                require(name not in seen and not item.is_dir() and not (item.flag_bits & 1)
                        and len(parts) >= 2 and parts[0] == recipe
                        and all(re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", part)
                                and part not in (".", "..") for part in parts)
                        and mode != 0o120000 and item.file_size <= MAX_UNPACKED,
                        "EVALUATOR_ZIP_MEMBER_UNSAFE")
                seen.add(name)
                total += item.file_size
                require(total <= MAX_UNPACKED, "EVALUATOR_ZIP_EXPANSION_LIMIT")
                payload = archive.read(item)
                require(len(payload) == item.file_size, "EVALUATOR_ZIP_MEMBER_MISMATCH")
                members.append({"path": name, "sha256": digest(payload), "bytes": len(payload)})
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise ValueError("EVALUATOR_ZIP_INVALID") from exc
    return {"member_count": len(members), "unpacked_bytes": total,
            "zip_crc_verified": True, "members": sorted(members, key=lambda x: x["path"])}


def run_f28_runtime(package_path, supplier_script):
    """Use the existing exact-hash, isolated F28 runtime tester; never run other ZIPs."""
    script = Path(supplier_script)
    require(script.is_file() and not script.is_symlink(), "EVALUATOR_SUPPLIER_RUNNER_MISSING")
    spec = importlib.util.spec_from_file_location("factory_quality_evidence_supplier", str(script))
    require(spec is not None and spec.loader is not None, "EVALUATOR_SUPPLIER_RUNNER_UNLOADABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.f28_runtime_proof(package_path)


def evaluate(dossier, package_path, catalog, supplier_script=None, runtime_runner=None):
    dossier = dict(dossier)
    require(dossier.get("schema") == SUPPLIER_SCHEMA, "EVALUATOR_DOSSIER_SCHEMA_INVALID")
    recipe = dossier.get("product_id")
    source = dossier.get("source_sha256")
    artifact = dossier.get("artifact_sha256")
    require(isinstance(recipe, str) and PRODUCT.fullmatch(recipe)
            and isinstance(source, str) and HEX.fullmatch(source)
            and isinstance(artifact, str) and HEX.fullmatch(artifact),
            "EVALUATOR_VERSION_ID_INVALID")
    package = Path(package_path)
    require(package.is_file() and not package.is_symlink()
            and 0 < package.stat().st_size <= MAX_PACKAGE, "EVALUATOR_PACKAGE_MISSING_OR_OVERSIZE")
    actual_sha = digest(package.read_bytes())
    require(actual_sha == artifact, "EVALUATOR_ARTIFACT_HASH_MISMATCH")

    ids = list(catalog)
    assignments = dossier.get("supplier_assignments")
    require(isinstance(assignments, dict) and list(assignments) == ids
            and dossier.get("criteria_total") == 100,
            "EVALUATOR_ASSIGNMENT_CATALOG_MISMATCH")
    for key, assignment in assignments.items():
        require(isinstance(assignment, dict) and assignment.get("criterion_id") == key,
                "EVALUATOR_ASSIGNMENT_ID_MISMATCH")

    zip_report = inspect_zip(package, recipe)
    claimed = dossier.get("automated_criteria_measured")
    require(isinstance(claimed, list) and len(claimed) == len(set(claimed))
            and all(isinstance(x, str) and x in assignments for x in claimed),
            "EVALUATOR_CLAIMED_CRITERIA_INVALID")
    accepted = {}
    rejected_claims = []
    recorded_zip = dossier.get("q068_original_warehouse_zip_measurement")
    if "Q068" in claimed:
        if recorded_zip == zip_report:
            accepted["Q068"] = {"scope": "actual_package_member_sha_crc_integrity",
                                  "measurement": zip_report}
        else:
            rejected_claims.append({"criterion_id": "Q068",
                                   "reason": "RECORDED_ZIP_MEASUREMENT_MISMATCH"})

    runtime = None
    runtime_claims = sorted(set(claimed).intersection(F28_CRITERIA))
    pinned = (recipe == F28_RECIPE and source == F28_SOURCE and artifact == F28_ARTIFACT)
    if runtime_claims and pinned:
        runner = runtime_runner or (lambda p: run_f28_runtime(p, supplier_script))
        try:
            measured = runner(package)
            recorded = dossier.get("f28_runtime_technical_measurement")
            require(isinstance(recorded, dict), "EVALUATOR_RUNTIME_RECEIPT_MISSING")
            checks = ("actual_embedded_unittest_count", "positive_baseline_cli_repeats",
                      "invalid_cli_inputs_rejected", "repeat_stdout_sha256")
            require(all(recorded.get(k) == measured.get(k) for k in checks),
                    "EVALUATOR_RUNTIME_RECEIPT_MISMATCH")
            runtime = measured
            for key in runtime_claims:
                accepted[key] = {"scope": "pinned_f28_runtime_test_only",
                                  "measurement": measured}
        except (OSError, RuntimeError, ValueError, KeyError) as exc:
            rejected_claims.extend({"criterion_id": key, "reason": "RUNTIME_RECHECK_FAILED"}
                                   for key in runtime_claims)
    elif runtime_claims:
        rejected_claims.extend({"criterion_id": key, "reason": "NOT_TRUSTED_PINNED_F28_BUILD"}
                               for key in runtime_claims)

    rows = {}
    for key, criterion in catalog.items():
        evidence = accepted.get(key)
        rows[key] = {
            "criterion": criterion["name"],
            "machine_evidence_state": "RECHECKED" if evidence else "NOT_ESTABLISHED",
            "machine_scope": evidence["scope"] if evidence else None,
            "measurement": evidence["measurement"] if evidence else None,
            "independent_quality_points": None,
            "human_review_required": True,
        }
    return {
        "schema": SCHEMA,
        "product_id": recipe,
        "source_sha256": source,
        "artifact_sha256": actual_sha,
        "supplier_dossier_canonical_sha256": digest(json.dumps(
            dossier, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf8")),
        "catalog_criteria_count": 100,
        "machine_evidence_rechecked_count": len(accepted),
        "machine_evidence_rechecked_criteria": sorted(accepted),
        "rejected_claims": rejected_claims,
        "criteria": rows,
        "professional_quality_points": None,
        "independent_reviewer_count": 0,
        "release_allowed": False,
        "publication_or_payment_enabled": False,
        "disposition": "HUMAN_REVIEW_REQUIRED",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dossier", "artifact", "catalog", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--supplier-script")
    args = parser.parse_args(argv)
    result = evaluate(read_json(args.dossier), args.artifact, load_catalog(args.catalog),
                      args.supplier_script)
    target = Path(args.output)
    require(not target.exists() and not target.is_symlink(), "EVALUATOR_OUTPUT_EXISTS")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf8") as stream:
        json.dump(result, stream, sort_keys=True, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    print("FACTORY_EVIDENCE_MACHINE_RECHECKED=" + str(result["machine_evidence_rechecked_count"]))
    print("FACTORY_EVIDENCE_PROFESSIONAL_POINTS=NONE")
    print("FACTORY_EVIDENCE_RELEASE_ALLOWED=false")
    print("FACTORY_EVIDENCE_EVALUATION_RECEIPT_SHA256=" + digest(target.read_bytes()))


if __name__ == "__main__":
    main()
