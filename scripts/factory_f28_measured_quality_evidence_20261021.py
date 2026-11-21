#!/usr/bin/env python3
"""Measured F28 quality evidence against real immutable warehouse ZIP.

Technical measurements only. Never impersonates independent specialists,
publishes a product, scores the 1000-point rubric, or edits warehouse stock.
"""
import argparse
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile
import zipfile

RECIPE = "greenhouse_crop_margin"
FILES = ("README.md", "calculator.py", "example_inputs.json", "test_calculator.py")
SCHEMA = "saeit.factory.f28-measured-technical-evidence.v1"
HEX = re.compile(r"^[0-9a-f]{64}$")
SEED = 20261021
VALID = 160
INVALID = 64
METAMORPHIC_CASES = 32
METAMORPHIC_RELATIONS = 4


def require(condition, code):
    if not condition:
        raise RuntimeError(code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def parse_file(path, limit=100000):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size < limit,
            "EVIDENCE_UNSAFE_JSON_FILE")
    return json.loads(path.read_text(encoding="utf-8"))


def money(number):
    return str(number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def oracle(item, output):
    require(output["market_data_independently_validated"] is False,
            "F28_UNVERIFIED_MARKET_DATA_INFLATED")
    data = output["results"]
    area = Decimal(str(item["area_m2"]))
    gross = area * Decimal(str(item["expected_yield_kg_per_m2"]))
    usable = gross * (1 - Decimal(str(item["rejection_rate_percent"])) / 100)
    price = Decimal(str(item["price_per_kg"]))
    if "variable_cost_per_m2" in item:
        variable_unit = Decimal(str(item["variable_cost_per_m2"]))
    else:
        variable_unit = sum((
            Decimal(str(item["water_liters_per_m2"])) * Decimal(str(item["water_cost_per_liter"])),
            Decimal(str(item["energy_kwh_per_m2"])) * Decimal(str(item["energy_cost_per_kwh"])),
            Decimal(str(item["labor_hours_per_m2"])) * Decimal(str(item["labor_cost_per_hour"])),
            Decimal(str(item["climate_control_kwh_per_m2"])) * Decimal(str(item["climate_control_cost_per_kwh"])),
            Decimal(str(item["other_variable_cost_per_m2"])),
        ))
    cost = area * variable_unit + Decimal(str(item["fixed_cost_total"]))
    revenue = usable * price
    expected = {"sales_revenue": money(revenue),
                "variable_cost_total": money(area * variable_unit),
                "total_cost": money(cost),
                "net_margin": money(revenue - cost)}
    for field, wanted in expected.items():
        require(data.get(field) == wanted, "F28_ORACLE_MISMATCH_" + field)
    threshold = data.get("break_even_price_per_kg")
    if usable == 0:
        require(threshold is None, "F28_UNREACHABLE_PRICE_WRONG")
    else:
        actual = Decimal(threshold)
        require(actual * usable >= cost, "F28_PRICE_UNDERCUT")
        if actual >= Decimal("0.01"):
            require((actual - Decimal("0.01")) * usable < cost,
                    "F28_PRICE_THRESHOLD_INACCURATE")
    required = data.get("minimum_gross_yield_kg_per_m2_to_break_even")
    factor = area * (1 - Decimal(str(item["rejection_rate_percent"])) / 100) * price
    if cost == 0:
        require(required == "0.000", "F28_ZERO_COST_THRESHOLD_WRONG")
    elif factor == 0:
        require(required is None, "F28_IMPOSSIBLE_YIELD_CLAIM")
    else:
        minimum = Decimal(required)
        require(minimum * factor >= cost, "F28_REQUIRED_YIELD_UNDERCUT")
        if minimum >= Decimal("0.001"):
            require((minimum - Decimal("0.001")) * factor < cost,
                    "F28_REQUIRED_YIELD_OVERSTATED")


def valid_case(rng, index):
    item = {
        "currency": "USD",
        "area_m2": rng.randint(1, 10000),
        "expected_yield_kg_per_m2": rng.randint(0, 40),
        "price_per_kg": str(Decimal(rng.randint(0, 5000)) / 100),
        "fixed_cost_total": rng.randint(0, 30000),
        "rejection_rate_percent": rng.randint(0, 100),
    }
    if index % 5 == 0:
        item.update({
            "crop": "tomato", "season": "spring",
            "water_liters_per_m2": 100, "water_cost_per_liter": "0.01",
            "energy_kwh_per_m2": 10, "energy_cost_per_kwh": "0.2",
            "labor_hours_per_m2": "0.5", "labor_cost_per_hour": 8,
            "climate_control_kwh_per_m2": 5, "climate_control_cost_per_kwh": "0.2",
            "other_variable_cost_per_m2": 7,
        })
    else:
        item["variable_cost_per_m2"] = str(Decimal(rng.randint(0, 5000)) / 100)
    return item


def invalid_case(index):
    original = {"currency": "USD", "area_m2": 1000, "expected_yield_kg_per_m2": 12,
                "price_per_kg": "2.5", "variable_cost_per_m2": 15,
                "fixed_cost_total": 5000, "rejection_rate_percent": 10}
    changes = (
        ("area_m2", 0), ("area_m2", "NaN"), ("area_m2", True),
        ("expected_yield_kg_per_m2", "Infinity"), ("price_per_kg", -1),
        ("rejection_rate_percent", 101), ("rejection_rate_percent", -1),
        ("currency", "not a code"), ("variable_cost_per_m2", "-Infinity"),
        ("fixed_cost_total", "not-a-number"),
    )
    field, value = changes[index % len(changes)]
    original[field] = value
    return original


def metamorphic_followups(item):
    """Four economic invariants, measured on the extracted real customer CLI."""
    price_up = dict(item, price_per_kg=str(
        Decimal(str(item["price_per_kg"])) + Decimal("1")))
    fixed_up = dict(item, fixed_cost_total=item["fixed_cost_total"] + 100)
    rejection_up = dict(item, rejection_rate_percent=min(
        100, item["rejection_rate_percent"] + 1))
    area_doubled = dict(item, area_m2=item["area_m2"] * 2)
    return (
        ("price_up", price_up),
        ("fixed_cost_up", fixed_up),
        ("rejection_up", rejection_up),
        ("area_doubled", area_doubled),
    )


def assert_metamorphic(relation, baseline, modified):
    before = baseline["results"]
    after = modified["results"]
    decimal = lambda row, field: Decimal(row[field])
    if relation == "price_up":
        require(decimal(after, "net_margin") >= decimal(before, "net_margin"),
                "F28_METAMORPHIC_PRICE_MARGIN")
        require(after["total_cost"] == before["total_cost"]
                and after["break_even_price_per_kg"] == before["break_even_price_per_kg"],
                "F28_METAMORPHIC_PRICE_COST_INVARIANT")
    elif relation == "fixed_cost_up":
        require(decimal(after, "total_cost") - decimal(before, "total_cost") == 100
                and decimal(before, "net_margin") - decimal(after, "net_margin") == 100,
                "F28_METAMORPHIC_FIXED_COST")
    elif relation == "rejection_up":
        require(decimal(after, "sales_revenue") <= decimal(before, "sales_revenue")
                and decimal(after, "net_margin") <= decimal(before, "net_margin")
                and after["total_cost"] == before["total_cost"],
                "F28_METAMORPHIC_REJECTION")
    elif relation == "area_doubled":
        require(decimal(after, "sales_revenue") >= decimal(before, "sales_revenue")
                and decimal(after, "variable_cost_total") >= decimal(before, "variable_cost_total"),
                "F28_METAMORPHIC_AREA_SCALING")
    else:
        raise RuntimeError("F28_UNKNOWN_METAMORPHIC_RELATION")


def run_cli(source, sample, folder):
    inp = folder / "scenario.json"
    inp.write_text(json.dumps(sample, sort_keys=True), encoding="utf8")
    proc = subprocess.run(
        [sys.executable, "-B", str(source), str(inp)],
        cwd=str(folder), capture_output=True, text=True, timeout=15,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    return proc


def validate_criteria(path):
    data = parse_file(path, 50000)
    groups = data.get("groups")
    require(data.get("group_count") == 100 and
            data.get("total_points") == 1000 and isinstance(groups, dict)
            and list(groups) == ["Q%03d" % i for i in range(1, 101)],
            "QUALITY_100_CRITERIA_INVALID")
    return groups


def assess(warehouse, expected_source, expected_artifact, criteria):
    require(HEX.fullmatch(expected_source) and HEX.fullmatch(expected_artifact),
            "INVALID_EXPECTED_SHA")
    warehouse = Path(warehouse)
    version = warehouse / "finished" / RECIPE / expected_source
    package = version / "product.zip"
    manifest_path = version / "warehouse_manifest.json"
    require(version.is_dir() and not version.is_symlink() and
            package.is_file() and not package.is_symlink(), "F28_STORED_PACKAGE_MISSING")
    manifest = parse_file(manifest_path)
    require(manifest.get("schema") == "saeit.factory.production-warehouse.v1"
            and manifest.get("product_id") == RECIPE
            and manifest.get("source_sha256") == expected_source
            and manifest.get("artifact_sha256") == expected_artifact
            and manifest.get("manufacturing_qc") == "passed"
            and manifest.get("commercial_release") is False
            and manifest.get("site_transfer_state") == "not_transferred"
            and manifest.get("bytes") == package.stat().st_size
            and digest(package.read_bytes()) == expected_artifact,
            "F28_STOCK_IDENTITY_OR_POLICY_MISMATCH")
    names = tuple(RECIPE + "/" + name for name in FILES)
    with tempfile.TemporaryDirectory(prefix="f28-measured-evidence-") as temp:
        directory = Path(temp)
        with zipfile.ZipFile(str(package)) as archive:
            listed = archive.namelist()
            require(sorted(listed) == sorted(names) and archive.testzip() is None,
                    "F28_ZIP_CRC_OR_CONTENTS_INVALID")
            for entry in archive.infolist():
                require(not entry.is_dir() and not entry.flag_bits & 0x1
                        and entry.file_size <= 400000
                        and not ((entry.external_attr >> 16) & 0o170000) == 0o120000,
                        "F28_ZIP_MEMBER_UNSAFE")
            for filename in FILES:
                (directory / filename).write_bytes(archive.read(RECIPE + "/" + filename))
        unit = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(directory),
             "-p", "test_calculator.py", "-v"],
            cwd=str(directory), capture_output=True, text=True, timeout=40,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        require(unit.returncode == 0 and "OK" in unit.stderr,
                "F28_EXTRACTED_PRODUCT_UNIT_TESTS_FAILED")
        measured_units = re.search(r"Ran ([0-9]+) tests?", unit.stderr)
        require(measured_units is not None and int(measured_units.group(1)) >= 1,
                "F28_UNIT_TEST_COUNT_UNVERIFIED")
        calculator = directory / "calculator.py"
        rng = random.Random(SEED)
        transcript = hashlib.sha256()
        for index in range(VALID):
            case = valid_case(rng, index)
            result = run_cli(calculator, case, directory)
            require(result.returncode == 0, "F28_VALID_CUSTOMER_CLI_FAILED")
            outcome = json.loads(result.stdout)
            oracle(case, outcome)
            transcript.update(json.dumps(
                [index, case, outcome], sort_keys=True, separators=(",", ":")).encode())
        for index in range(INVALID):
            case = invalid_case(index)
            result = run_cli(calculator, case, directory)
            require(result.returncode == 2 and result.stdout == ""
                    and "INPUT_ERROR:" in result.stderr,
                    "F28_INVALID_CUSTOMER_INPUT_NOT_REJECTED")
            transcript.update(json.dumps(
                ["invalid", index, case, result.returncode],
                sort_keys=True, separators=(",", ":")).encode())
        # Behavioral checks beyond isolated arithmetic examples. These cannot
        # prove market data, professional field validity or global superiority.
        metamorphic_rng = random.Random(SEED + 1000)
        for index in range(METAMORPHIC_CASES):
            base = valid_case(metamorphic_rng, index)
            initial = run_cli(calculator, base, directory)
            require(initial.returncode == 0, "F28_METAMORPHIC_BASELINE_CLI_FAILED")
            baseline = json.loads(initial.stdout)
            oracle(base, baseline)
            for relation, changed in metamorphic_followups(base):
                output = run_cli(calculator, changed, directory)
                require(output.returncode == 0, "F28_METAMORPHIC_CUSTOMER_CLI_FAILED")
                actual = json.loads(output.stdout)
                oracle(changed, actual)
                assert_metamorphic(relation, baseline, actual)
                transcript.update(json.dumps(
                    ["metamorphic", index, relation, base, changed, baseline, actual],
                    sort_keys=True, separators=(",", ":")).encode())
    groups = validate_criteria(criteria)
    return {
        "schema": SCHEMA, "family_id": "F28", "recipe": RECIPE,
        "source_sha256": expected_source, "artifact_sha256": expected_artifact,
        "warehouse_manifest_sha256": digest(manifest_path.read_bytes()),
        "evidence_runner_sha256": digest(Path(__file__).read_bytes()),
        "source": "actual_hash_verified_private_finished_warehouse_zip",
        "actual_package_bytes": package.stat().st_size,
        "zip_member_count": len(FILES), "zip_crc_checked": True,
        "extracted_product_unit_tests": "passed",
        "extracted_product_unit_test_count": int(measured_units.group(1)),
        "valid_real_customer_cli_scenarios_oracle_checked": VALID,
        "invalid_customer_cli_scenarios_rejected": INVALID,
        "metamorphic_customer_scenario_pairs_checked": METAMORPHIC_CASES * METAMORPHIC_RELATIONS,
        "metamorphic_properties": [
            "higher_price_cannot_lower_margin",
            "higher_fixed_cost_lowers_margin_exactly",
            "higher_rejection_cannot_increase_revenue_or_margin",
            "double_area_cannot_lower_revenue_or_variable_cost",
        ],
        "reproducible_seed": SEED, "test_transcript_sha256": transcript.hexdigest(),
        "market_observations_independently_validated": False,
        "real_customer_field_validation_completed": False,
        "professional_agronomic_economics_review_completed": False,
        "rights_and_licenses_independently_cleared": False,
        "independent_authenticated_review_completed": False,
        "quality_criteria_total": len(groups),
        "quality_criteria_catalog_sha256": digest(Path(criteria).read_bytes()),
        "quality_criteria_not_independently_approved": list(groups),
        "technical_evidence_for": {
            "Q068": "zip_member_integrity_sha_and_crc",
            "Q033": "calculation_arithmetic_oracle_only_not_scientific_field_accuracy",
        },
        "professional_1000_quality_points": None,
        "professional_1000_quality_approved": False,
        "customer_publication_allowed": False,
        "payment_enabled": False,
        "disposition": "TECHNICAL_PROOF_COMPLETE_EXPERT_FIELD_RIGHTS_REVIEW_PENDING",
    }


def store(root, report):
    root = Path(root)
    folder = (root / "quality-excellence" / "private-measured-evidence"
              / "F28" / report["artifact_sha256"])
    require(not folder.is_symlink(), "EVIDENCE_DIRECTORY_SYMLINK")
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    raw = (json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()
    key = report["evidence_runner_sha256"]
    target = folder / ("technical-" + key + ".json")
    require(not target.is_symlink(), "EVIDENCE_FILE_SYMLINK")
    if target.exists():
        require(target.is_file() and target.read_bytes() == raw,
                "EVIDENCE_IMMUTABILITY_CONFLICT")
    else:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(str(target), flags, 0o600)
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
    require(target.read_bytes() == raw, "EVIDENCE_FINAL_READBACK_MISMATCH")
    return {"path": str(target), "sha256": digest(raw), "artifact_sha256": report["artifact_sha256"],
            "valid_scenarios": VALID, "invalid_scenarios": INVALID,
            "metamorphic_pairs": METAMORPHIC_CASES * METAMORPHIC_RELATIONS,
            "commercial_release_allowed": False, "quality_1000_certified": False}


def selftest():
    repo = Path(__file__).resolve().parents[1]
    sample = repo / "product_recipes" / RECIPE
    with tempfile.TemporaryDirectory(prefix="f28-evidence-selftest-") as folder:
        root = Path(folder)
        version = root / "production-warehouse" / "finished" / RECIPE / ("a" * 64)
        version.mkdir(parents=True)
        package = version / "product.zip"
        with zipfile.ZipFile(str(package), "w", zipfile.ZIP_DEFLATED) as archive:
            for filename in FILES:
                archive.write(str(sample / filename), RECIPE + "/" + filename)
        digest_value = digest(package.read_bytes())
        (version / "warehouse_manifest.json").write_text(json.dumps({
            "schema": "saeit.factory.production-warehouse.v1",
            "product_id": RECIPE, "source_sha256": "a" * 64,
            "artifact_sha256": digest_value, "manufacturing_qc": "passed",
            "commercial_release": False, "site_transfer_state": "not_transferred",
            "bytes": package.stat().st_size,
        }))
        report = assess(root / "production-warehouse", "a" * 64, digest_value,
                        repo / "factory_config" / "quality_100_criteria.json")
        assert report["valid_real_customer_cli_scenarios_oracle_checked"] == VALID
        assert report["invalid_customer_cli_scenarios_rejected"] == INVALID
        assert report["metamorphic_customer_scenario_pairs_checked"] == (
            METAMORPHIC_CASES * METAMORPHIC_RELATIONS)
        assert report["professional_1000_quality_approved"] is False
        assert store(root, report) == store(root, report)
        try:
            assess(root / "production-warehouse", "a" * 64, "b" * 64,
                   repo / "factory_config" / "quality_100_criteria.json")
        except RuntimeError as e:
            assert "MISMATCH" in str(e)
        else:
            raise AssertionError("Fake package hash accepted")
    print("F28_MEASURED_EVIDENCE_SELFTEST=PASS")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--factory-root")
    parser.add_argument("--source-sha256")
    parser.add_argument("--artifact-sha256")
    parser.add_argument("--criteria")
    args = parser.parse_args()
    if args.selftest:
        selftest()
    else:
        require(all((args.factory_root, args.source_sha256, args.artifact_sha256, args.criteria)),
                "F28_EVIDENCE_ARGUMENTS_MISSING")
        report = assess(Path(args.factory_root) / "production-warehouse",
                        args.source_sha256, args.artifact_sha256, args.criteria)
        summary = store(args.factory_root, report)
        print("F28_VPS_MEASURED_QUALITY_EVIDENCE=" + json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
