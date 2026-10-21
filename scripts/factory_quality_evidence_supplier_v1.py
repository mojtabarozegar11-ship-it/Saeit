#!/usr/bin/env python3
"""Actual evidence supplier for 100x10 quality obligations.

The automated supplier currently performs one real, scope-limited measurement:
Q068, integrity and CRC verification of a finished, hash-locked warehouse ZIP.
It assigns concrete *supplier roles* for all 100 criteria, but does not invent
connected third parties, empirical user tests, expert opinions or 1000 points.
No store, payments, approvals, or warehouse versions are modified.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import zipfile

SCHEMA = "saeit.factory.quality-evidence-supply.v1"
HEX = re.compile(r"^[a-f0-9]{64}$")
PRODUCT = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
ROLES = (
    ("market_benchmark_supplier", "current real competitor and market measurement", "independent market research required"),
    ("innovation_provenance_supplier", "original build history, novelty research, independently checked ownership", "prior-art and originality confirmation required"),
    ("engineering_test_supplier", "reproducible engineering, profiling and integration tests", "automated builds plus independent reproducibility"),
    ("domain_specialist_supplier", "scientific field observations and qualified discipline review", "externally authenticated domain expert and real data"),
    ("customer_research_supplier", "consenting genuine user tasks, outcomes and blind feedback", "real users and privacy-respecting recordings"),
    ("ux_accessibility_supplier", "multi-device sessions, accessibility findings and regressions", "real hardware and independent accessibility testing"),
    ("adversarial_qa_supplier", "fault, recovery, reproducibility and actual ZIP validation", "tool evidence plus independent adversarial review"),
    ("security_rights_supplier", "security assessment, chain of title and licence permission", "independent security/legal specialist"),
    ("commerce_operations_supplier", "actual permitted order, entitlement, support and delivery tests", "sandbox commerce plus owner-only release approval"),
    ("independent_review_supplier", "authenticated unbiased reviewers, repeatability and signed final verdict", "owner-pinned reviewer trust and external signatures"),
)
EXTERNAL_REQUIRED = {
    "market_benchmark_supplier", "domain_specialist_supplier",
    "customer_research_supplier", "security_rights_supplier",
    "independent_review_supplier",
}
MAX_PACKAGE = 25 * 1024 * 1024
MAX_MEMBERS = 100
MAX_UNPACKED = 40 * 1024 * 1024


def require(ok, code):
    if not ok:
        raise RuntimeError(code)


def hash_bytes(value):
    return hashlib.sha256(value).hexdigest()


def read_json(path, size=200000):
    p = Path(path)
    require(p.is_file() and not p.is_symlink() and 0 < p.stat().st_size <= size,
            "SUPPLIER_JSON_UNSAFE")
    doc = json.loads(p.read_text(encoding="utf8"))
    require(isinstance(doc, dict), "SUPPLIER_JSON_INVALID")
    return doc


def catalog(path):
    data = read_json(path)
    groups = data.get("groups")
    require(data.get("schema") == "saeit.factory.quality-100-groups.v2"
            and data.get("group_count") == 100
            and data.get("points_per_group") == 10
            and data.get("total_points") == 1000
            and isinstance(groups, dict)
            and list(groups) == ["Q%03d" % i for i in range(1, 101)],
            "SUPPLIER_CATALOG_CONTRACT_INVALID")
    require(all(isinstance(x.get("name"), str) and x.get("maximum_points") == 10
                and isinstance(x.get("quality_dimensions"), list)
                for x in groups.values()), "SUPPLIER_CATALOG_CRITERION_INVALID")
    return groups


def supplier_route(criterion, policy, measured=None):
    n = int(criterion[1:])
    role, output, review = ROLES[(n - 1) // 10]
    measured = measured if measured is not None else {"Q068"}
    return {
        "criterion_id": criterion,
        "criterion_name": policy["name"],
        "possible_supplier_role": role,
        "required_output": output,
        "independent_review_dependency": review,
        "person_or_company_contractually_connected": False,
        "supplier_identity_authenticated": False,
        "supplier_authorized_to_sign": False,
        "automated_evidence_executable_now": criterion in measured,
        "engine": ("scripts/factory_quality_evidence_supplier_v1.py"
                   if criterion in measured else None),
        "required_evidence_state": "MEASURED_PARTIAL_TECHNICAL_EVIDENCE" if criterion in measured
                                  else "AWAITING_REAL_SUPPLIER_WORK",
        "professional_points_awarded": None,
    }


def zip_proof(file, recipe):
    require(file.is_file() and not file.is_symlink() and
            0 < file.stat().st_size <= MAX_PACKAGE, "SUPPLIER_PACKAGE_UNSAFE")
    members = []
    total = 0
    with zipfile.ZipFile(str(file)) as archive:
        items = archive.infolist()
        require(0 < len(items) <= MAX_MEMBERS and archive.testzip() is None,
                "SUPPLIER_ZIP_CRC_FAILED")
        seen = set()
        for item in items:
            name = item.filename
            parts = name.split("/")
            require(name not in seen and not item.is_dir()
                    and not (item.flag_bits & 0x1)
                    and len(parts) >= 2 and parts[0] == recipe
                    and all(re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", p)
                            and p not in (".", "..") for p in parts)
                    and item.file_size <= MAX_UNPACKED
                    and (item.external_attr >> 16) & 0o170000 != 0o120000,
                    "SUPPLIER_ZIP_UNSAFE_MEMBER")
            seen.add(name)
            total += item.file_size
            require(total <= MAX_UNPACKED, "SUPPLIER_ZIP_EXPANSION_LIMIT")
            payload = archive.read(item)
            require(len(payload) == item.file_size, "SUPPLIER_ZIP_MEMBER_MISMATCH")
            members.append({
                "path": name, "sha256": hash_bytes(payload), "bytes": item.file_size
            })
    return {"members": sorted(members, key=lambda x: x["path"]),
            "member_count": len(members), "unpacked_bytes": total,
            "zip_crc_verified": True}



# This specific archive has already passed the factory's separate technical
# verification. Executing ZIP-contained Python on the VPS is restricted to
# this exact hash-pinned private F28 product; never run arbitrary warehouse ZIPs.
PINNED_F28_SOURCE = "c446aeaa32494c93a453f524390ee14061d6f36da3228b3d4b15c5b794d2bc1e"
PINNED_F28_ARTIFACT = "7ba2168c90617b236d10ee4542ec9fd276f3f524809ddd001f18f5a5634fc553"
F28_FILES = ("README.md", "calculator.py", "example_inputs.json", "test_calculator.py")
RUNTIME_SCOPES = {
    "Q036": "actual_cli_discloses_hypothetical_inputs_and_uncalibrated_market_limits_only",
    "Q057": "malformed_inputs_get_bounded_non_traceback_errors_only_not_ux_recovery",
    "Q061": "actual_cli_arithmetic_baseline_validated_only",
    "Q064": "embedded_unittest_suite_on_exact_zip_executed_only",
    "Q069": "eight_repeat_cold_start_cli_consistency_only_not_long_duration_stability",
}


def f28_runtime_proof(archive_path):
    """Real cold-start CLI and embedded tests on a trusted, pinned F28 ZIP."""
    import subprocess
    import sys
    import tempfile
    import time
    require(hash_bytes(Path(archive_path).read_bytes()) == PINNED_F28_ARTIFACT,
            "F28_RUNTIME_REQUIRES_PINNED_PRODUCT_SHA")
    with tempfile.TemporaryDirectory(prefix="f28-qa1000-runtime-") as tmp:
        base = Path(tmp)
        with zipfile.ZipFile(str(archive_path)) as bundle:
            names = sorted(bundle.namelist())
            require(names == sorted("greenhouse_crop_margin/" + n for n in F28_FILES),
                    "F28_RUNTIME_ZIP_SOURCE_INCOMPLETE")
            for name in F28_FILES:
                item = bundle.getinfo("greenhouse_crop_margin/" + name)
                require(item.file_size <= 400000 and not item.is_dir()
                        and (item.external_attr >> 16) & 0o170000 != 0o120000,
                        "F28_RUNTIME_UNSAFE_MEMBER")
                (base / name).write_bytes(bundle.read(item))
        calc = base / "calculator.py"
        unit = subprocess.run(
            [sys.executable, "-I", "-B", "-m", "unittest", "discover",
             "-s", str(base), "-p", "test_calculator.py", "-v"],
            cwd=str(base), capture_output=True, text=True, timeout=35)
        match = re.search(r"Ran ([0-9]+) tests?", unit.stderr)
        require(unit.returncode == 0 and match is not None and
                int(match.group(1)) > 0 and "OK" in unit.stderr,
                "F28_RUNTIME_EMBEDDED_REGRESSION_FAILED")
        source = base / "scenario.json"
        item = read_json(base / "example_inputs.json")
        source.write_text(json.dumps(item), encoding="utf8")
        checks = []
        for _ in range(8):
            started = time.monotonic_ns()
            run = subprocess.run([sys.executable, "-I", "-B", str(calc), str(source)],
                cwd=str(base), capture_output=True, text=True, timeout=12)
            milliseconds = round((time.monotonic_ns() - started) / 1_000_000, 2)
            require(run.returncode == 0 and len(run.stdout) < 100000,
                    "F28_RUNTIME_CUSTOMER_CLI_FAILED")
            output = json.loads(run.stdout)
            values = output["results"]
            require(values["sales_revenue"] == "27000.00"
                    and values["total_cost"] == "20000.00"
                    and values["net_margin"] == "7000.00",
                    "F28_RUNTIME_INDEPENDENT_BASELINE_MISMATCH")
            require(output.get("market_data_independently_validated") is False
                    and len(output.get("assumptions", [])) >= 3
                    and any("not guaranteed" in str(x).lower()
                            for x in output["assumptions"]),
                    "F28_RUNTIME_ASSUMPTIONS_MISLEADING")
            checks.append({"output_sha256": hash_bytes(run.stdout.encode()),
                           "cold_start_ms": milliseconds})
        require(len(set(v["output_sha256"] for v in checks)) == 1,
                "F28_RUNTIME_NONDETERMINISTIC_OUTPUT")
        invalid = 0
        for field, value in (("area_m2", 0), ("area_m2", "NaN"),
                             ("price_per_kg", "Infinity"), ("price_per_kg", -1),
                             ("rejection_rate_percent", 101),
                             ("fixed_cost_total", "-Infinity"),
                             ("variable_cost_per_m2", "nonsense"),
                             ("expected_yield_kg_per_m2", True)):
            payload = dict(item)
            payload[field] = value
            source.write_text(json.dumps(payload), encoding="utf8")
            run = subprocess.run([sys.executable, "-I", "-B", str(calc), str(source)],
                cwd=str(base), capture_output=True, text=True, timeout=12)
            require(run.returncode == 2 and not run.stdout
                    and run.stderr.startswith("INPUT_ERROR:")
                    and "Traceback" not in run.stderr, "F28_RUNTIME_BAD_INPUT_NOT_HANDLED")
            invalid += 1
        return {
            "actual_embedded_unittest_count": int(match.group(1)),
            "positive_baseline_cli_repeats": len(checks),
            "invalid_cli_inputs_rejected": invalid,
            "repeat_stdout_sha256": checks[0]["output_sha256"],
            "cold_start_max_ms": max(x["cold_start_ms"] for x in checks),
            "limited_scope_only": True,
            "real_hardware_stress_and_long_term_runtime_unmeasured": True,
            "external_domain_review_complete": False,
        }


def supplier_dossier(root, policy, recipe, source_sha, artifact_sha):
    require(PRODUCT.fullmatch(recipe) and HEX.fullmatch(source_sha)
            and HEX.fullmatch(artifact_sha), "SUPPLIER_VERSION_ID_INVALID")
    root = Path(root)
    warehouse = root / "production-warehouse"
    version = warehouse / "finished" / recipe / source_sha
    require(version.is_dir() and not version.is_symlink()
            and not warehouse.is_symlink(), "SUPPLIER_VERSION_NOT_PRESENT")
    saved = read_json(version / "warehouse_manifest.json")
    archive = version / "product.zip"
    require(archive.is_file() and not archive.is_symlink() and
            0 < archive.stat().st_size <= MAX_PACKAGE,
            "SUPPLIER_PACKAGE_UNSAFE")
    require(saved.get("schema") == "saeit.factory.production-warehouse.v1"
            and saved.get("product_id") == recipe
            and saved.get("source_sha256") == source_sha
            and saved.get("artifact_sha256") == artifact_sha
            and saved.get("manufacturing_qc") == "passed"
            and saved.get("commercial_release") is False
            and saved.get("site_transfer_state") == "not_transferred"
            and saved.get("bytes") == archive.stat().st_size
            and hash_bytes(archive.read_bytes()) == artifact_sha,
            "SUPPLIER_WAREHOUSE_VERSION_HASH_OR_POLICY_MISMATCH")
    measured = zip_proof(archive, recipe)
    scopes = {"Q068": "actual_package_integrity_crc_sha_only"}
    runtime = None
    if (recipe == "greenhouse_crop_margin" and
        source_sha == PINNED_F28_SOURCE and artifact_sha == PINNED_F28_ARTIFACT):
        runtime = f28_runtime_proof(archive)
        scopes.update(RUNTIME_SCOPES)
    routes = {
        key: supplier_route(key, value, scopes) for key, value in policy.items()
    }
    return {
        "schema": SCHEMA,
        "product_id": recipe,
        "source_sha256": source_sha,
        "artifact_sha256": artifact_sha,
        "warehouse_manifest_sha256": hash_bytes(
            (version / "warehouse_manifest.json").read_bytes()),
        "criteria_total": len(routes),
        "possible_supplier_roles": sorted(set(x["possible_supplier_role"]
                                              for x in routes.values())),
        "genuinely_connected_external_supplier_count": 0,
        "automated_technical_suppliers_executed": 1 if runtime is None else 2,
        "automated_criteria_measured": sorted(scopes),
        "measured_criterion_scope_limits": scopes,
        "f28_runtime_technical_measurement": runtime,
        "q068_original_warehouse_zip_measurement": measured,
        "supplier_assignments": routes,
        "unmet_criterion_count": 100 - len(scopes),
        "independently_unapproved_criterion_count": 100,
        "independent_external_assessments_completed": 0,
        "professional_quality_1000_points": None,
        "professional_quality_1000_certified": False,
        "sale_or_publication_allowed": False,
        "original_warehouse_modified": False,
    }


def persist(root, dossier):
    root = Path(root)
    folder = (root / "quality-excellence" / "evidence-suppliers"
              / dossier["product_id"] / dossier["source_sha256"])
    require(not folder.is_symlink() and
            not (folder.parent.exists() and folder.parent.is_symlink()),
            "SUPPLIER_OUTPUT_SYMLINK")
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    raw = (json.dumps(dossier, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()
    receipt = folder / ("supply-" + hash_bytes(raw) + ".json")
    require(not receipt.is_symlink(), "SUPPLIER_RECEIPT_SYMLINK")
    if receipt.exists():
        require(receipt.is_file() and receipt.read_bytes() == raw,
                "SUPPLIER_IMMUTABLE_RECEIPT_CONFLICT")
    else:
        flags = os.O_CREAT | os.O_WRONLY | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(str(receipt), flags, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
    require(hash_bytes(receipt.read_bytes()) == hash_bytes(raw),
            "SUPPLIER_RECEIPT_READBACK_FAILED")
    return {
        "product_id": dossier["product_id"],
        "artifact_sha256": dossier["artifact_sha256"],
        "receipt": str(receipt),
        "receipt_sha256": hash_bytes(raw),
        "criteria_assigned": len(dossier["supplier_assignments"]),
        "genuine_technical_evidence_supplied": len(dossier["automated_criteria_measured"]),
        "measured_criteria": dossier["automated_criteria_measured"],
        "external_independent_evidence_pending": True,
        "quality_1000_certified": False,
        "public_release_allowed": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-root", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--recipe", required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--artifact-sha256", required=True)
    args = parser.parse_args()
    proof = supplier_dossier(
        args.factory_root, catalog(args.catalog), args.recipe,
        args.source_sha256, args.artifact_sha256)
    print("FACTORY_QA1000_EVIDENCE_SUPPLIER=" + json.dumps(
        persist(args.factory_root, proof), sort_keys=True))


if __name__ == "__main__":
    main()
