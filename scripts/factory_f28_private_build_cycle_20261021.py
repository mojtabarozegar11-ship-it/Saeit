#!/usr/bin/env python3
"""F28 private build -> independent customer smoke -> mechanical repair -> recheck.

Only source-controlled inputs are executed. Technical status is never a signed
agronomic review, quality 1000 clearance, listing, or permission to sell.
"""
import argparse
from decimal import Decimal
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

RECIPE = "greenhouse_crop_margin"
FILES = ("README.md", "calculator.py", "example_inputs.json", "test_calculator.py")
SCHEMA = "zomorodmelal.factory.f28-private-build-cycle.v1"


class TechnicalDefect(Exception):
    def __init__(self, code, explanation):
        super().__init__(explanation)
        self.code = code


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_private(path, data):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("UNSAFE_PRIVATE_RECEIPT")
    temporary = path.with_name(path.name + ".new")
    if temporary.exists() or temporary.is_symlink():
        raise ValueError("RECEIPT_TEMPORARY_CONFLICT")
    with temporary.open("x", encoding="utf8") as stream:
        json.dump(data, stream, sort_keys=True, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def validate_output(output, inputs):
    """Compute an oracle without importing the product's calculation function."""
    values = output["results"]
    area = Decimal(str(inputs["area_m2"]))
    amount = Decimal(str(inputs["expected_yield_kg_per_m2"]))
    price = Decimal(str(inputs["price_per_kg"]))
    rate = Decimal(str(inputs.get("rejection_rate_percent", 0)))
    saleable = area * amount * (1 - rate / 100)
    revenue = saleable * price
    if "variable_cost_per_m2" in inputs:
        unit_cost = Decimal(str(inputs["variable_cost_per_m2"]))
    else:
        unit_cost = (
            Decimal(str(inputs["water_liters_per_m2"])) * Decimal(str(inputs["water_cost_per_liter"]))
            + Decimal(str(inputs["energy_kwh_per_m2"])) * Decimal(str(inputs["energy_cost_per_kwh"]))
            + Decimal(str(inputs["labor_hours_per_m2"])) * Decimal(str(inputs["labor_cost_per_hour"]))
            + Decimal(str(inputs["climate_control_kwh_per_m2"])) * Decimal(str(inputs["climate_control_cost_per_kwh"]))
            + Decimal(str(inputs["other_variable_cost_per_m2"]))
        )
    cost = area * unit_cost + Decimal(str(inputs["fixed_cost_total"]))
    cent = Decimal("0.01")
    if abs(Decimal(values["sales_revenue"]) - revenue) > cent / 2:
        raise TechnicalDefect("F28_REVENUE_ORACLE_MISMATCH", "Independent revenue calculation differs")
    if abs(Decimal(values["total_cost"]) - cost) > cent / 2:
        raise TechnicalDefect("F28_COST_ORACLE_MISMATCH", "Independent cost calculation differs")
    if abs(Decimal(values["net_margin"]) - (revenue - cost)) > cent / 2:
        raise TechnicalDefect("F28_MARGIN_ORACLE_MISMATCH", "Independent margin calculation differs")
    if saleable > 0:
        threshold = Decimal(values["break_even_price_per_kg"])
        if threshold * saleable < cost:
            raise TechnicalDefect("F28_BREAK_EVEN_UNDERCUT", "Reported price still produces a loss")
        if threshold >= cent and (threshold - cent) * saleable >= cost:
            raise TechnicalDefect("F28_BREAK_EVEN_INACCURATE", "Price threshold is overstated")
    else:
        if values["break_even_price_per_kg"] is not None:
            raise TechnicalDefect("F28_UNREACHABLE_PRICE", "Zero saleable yield must not have a break-even price")
    required = values["minimum_gross_yield_kg_per_m2_to_break_even"]
    factor = area * (1 - rate / 100) * price
    if cost == 0:
        if required is None or Decimal(required) != 0:
            raise TechnicalDefect("F28_ZERO_COST_THRESHOLD", "Zero cost requires zero harvest threshold")
    elif factor == 0:
        if required is not None:
            raise TechnicalDefect("F28_UNREACHABLE_YIELD", "Unreachable harvest threshold was claimed")
    else:
        if required is None:
            raise TechnicalDefect("F28_MISSING_YIELD", "Missing harvest threshold")
        minimum = Decimal(required)
        if minimum * factor < cost:
            raise TechnicalDefect("F28_YIELD_UNDERCUT", "Reported harvest does not cover costs")
        if minimum >= Decimal("0.001") and (minimum - Decimal("0.001")) * factor >= cost:
            raise TechnicalDefect("F28_YIELD_INACCURATE", "Harvest threshold is overstated")
    if output["market_data_independently_validated"] is not False:
        raise TechnicalDefect("F28_UNVERIFIED_MARKET_CLAIM", "Unverified market input must remain unverified")


def verify_customer_package(artifact, manifest):
    """Independent hash/ZIP/path/CLI audit of the exact end-user delivery bytes."""
    if not artifact.is_file() or artifact.is_symlink() or artifact.stat().st_size > 3_000_000:
        raise TechnicalDefect("F28_PACKAGE_MISSING", "Package is absent or unsafe")
    if manifest.get("artifact_sha256") != digest(artifact):
        raise TechnicalDefect("F28_ARTIFACT_HASH_MISMATCH", "Package no longer matches approved manifest")
    if manifest.get("qa_status") != "passed" or manifest.get("professional_quality_approved") is not False:
        raise TechnicalDefect("F28_MANUFACTURER_QA_INVALID", "No valid private technical QA status")
    expected = [RECIPE + "/" + name for name in FILES]
    try:
        with zipfile.ZipFile(artifact) as archive:
            if sorted(archive.namelist()) != expected or archive.testzip() is not None:
                raise TechnicalDefect("F28_ZIP_CONTENTS_INVALID", "ZIP contents or CRC differ from recipe")
            with tempfile.TemporaryDirectory(prefix="f28-customer-") as folder:
                temp = Path(folder)
                for name in FILES:
                    raw = archive.read(RECIPE + "/" + name)
                    if len(raw) > 400_000:
                        raise TechnicalDefect("F28_PACKAGE_FILE_OVERSIZE", "Unbounded recipe file")
                    (temp / name).write_bytes(raw)
                cases = [
                    json.loads((temp / "example_inputs.json").read_text(encoding="utf8")),
                    {"currency":"USD","area_m2":1000,"expected_yield_kg_per_m2":12,
                     "price_per_kg":2.5,"fixed_cost_total":5000,"rejection_rate_percent":10,
                     "crop":"tomato","season":"spring","water_liters_per_m2":100,
                     "water_cost_per_liter":0.01,"energy_kwh_per_m2":10,
                     "energy_cost_per_kwh":0.2,"labor_hours_per_m2":0.5,
                     "labor_cost_per_hour":8,"climate_control_kwh_per_m2":5,
                     "climate_control_cost_per_kwh":0.2,"other_variable_cost_per_m2":7},
                ]
                for scenario in cases:
                    sample = temp / "scenario.json"
                    sample.write_text(json.dumps(scenario), encoding="utf8")
                    result = subprocess.run([sys.executable, "-B", str(temp / "calculator.py"), str(sample)],
                                            capture_output=True, text=True, cwd=str(temp), timeout=15,
                                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
                    if result.returncode:
                        raise TechnicalDefect("F28_CUSTOMER_EXECUTION_FAILED", result.stderr[-350:])
                    try:
                        output = json.loads(result.stdout)
                        validate_output(output, scenario)
                    except (ValueError, KeyError, TypeError) as exc:
                        raise TechnicalDefect("F28_CUSTOMER_OUTPUT_INVALID", str(exc)[:350]) from exc
    except (OSError, zipfile.BadZipFile, subprocess.TimeoutExpired) as exc:
        raise TechnicalDefect("F28_CUSTOMER_PACKAGE_UNUSABLE", str(exc)[:350]) from exc
    return {"customer_scenarios_verified":2,"independent_arithmetic_oracle":True,
            "zip_integrity_verified":True,"customer_cli_from_extracted_zip":True}


def build_cycle(source, maker_file, out, *, revision="local"):
    source, maker_file, out = Path(source), Path(maker_file), Path(out)
    if source.is_symlink() or not source.is_dir() or source.name != RECIPE:
        raise ValueError("F28_SOURCE_ROOT_INVALID")
    for name in FILES:
        path = source / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("F28_SOURCE_FILE_MISSING_OR_UNSAFE:" + name)
    if maker_file.is_symlink() or not maker_file.is_file():
        raise ValueError("F28_MANUFACTURER_MISSING")
    if not (maker_file.parent / "factory_personal_owner_passport_policy_20261020.py").is_file():
        raise ValueError("F28_PASSPORT_DEPENDENCY_MISSING")
    if out.is_symlink():
        raise ValueError("F28_PRIVATE_STOCK_SYMLINK")
    out.mkdir(parents=True, mode=0o700, exist_ok=True)
    spec = importlib.util.spec_from_file_location("f28_pinned_manufacturer", str(maker_file))
    maker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(maker)
    stock = out / "private-stock" / RECIPE
    artifact = stock / (RECIPE + "-internal-qa.zip")
    manifest_file = stock / "manufacturing_manifest.json"
    corruption_detected = False
    if artifact.is_file() and not artifact.is_symlink() and manifest_file.is_file():
        try:
            prior = json.loads(manifest_file.read_text(encoding="utf8"))
            corruption_detected = prior.get("artifact_sha256") != digest(artifact)
        except (ValueError, OSError):
            corruption_detected = True
    common = {"schema":SCHEMA,"recipe":RECIPE,"source_commit":revision,
              "independent_professional_quality_1000_passed":False,
              "commercial_release_authorized":False,"public_listing_enabled":False}
    try:
        maker.manufacture(RECIPE, source.parent, out / "private-stock")
        manifest = json.loads(manifest_file.read_text(encoding="utf8"))
        _, files = maker.inspect_recipe(source)
        source_digest = maker.source_digest(source, files)
        if manifest.get("source_sha256") != source_digest:
            raise TechnicalDefect("F28_SOURCE_MANIFEST_MISMATCH", "Source bytes do not match manifest")
        blackbox = verify_customer_package(artifact, manifest)
        receipt = dict(common, status="private_technical_candidate_verified",
                       source_sha256=source_digest, artifact_sha256=digest(artifact),
                       technical_tests=manifest["qa_measurements"]["successful_tests"],
                       mechanical_repair_performed=corruption_detected,
                       independent_black_box_checks=blackbox)
        write_private(out / "private-cycle-receipt.json", receipt)
        if corruption_detected:
            write_private(out / "private-rework-order.json",
                          dict(common, status="technical_mechanical_repair_verified",
                               defect_code="F28_ARTIFACT_HASH_MISMATCH",
                               repaired_artifact_sha256=receipt["artifact_sha256"]))
        return receipt
    except (RuntimeError, OSError, ValueError, KeyError, TechnicalDefect) as exc:
        code = exc.code if isinstance(exc, TechnicalDefect) else "F28_SOURCE_OR_BUILD_REWORK_REQUIRED"
        order = dict(common, status="source_or_delivery_rework_required",
                     defect_code=code, explanation=str(exc)[:350])
        write_private(out / "private-rework-order.json", order)
        receipt = dict(common, status="blocked_rework_required", defect_code=code)
        write_private(out / "private-cycle-receipt.json", receipt)
        return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--maker", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--revision", default="local")
    args = parser.parse_args()
    result = build_cycle(args.source, args.maker, args.out, revision=args.revision)
    print("F28_PRIVATE_MANUFACTURE_RESULT=" + json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "private_technical_candidate_verified" else 2


if __name__ == "__main__":
    sys.exit(main())
