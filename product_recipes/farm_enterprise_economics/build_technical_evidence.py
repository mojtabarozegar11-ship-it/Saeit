#!/usr/bin/env python3
"""Capture real, product-bound technical evidence without awarding QC1000 points.

Run offline with Python 3.8+. This is a measured *candidate dossier*, not an
independent reviewer signature or commercial release. No GitHub or VPS runner
is required at runtime. An evidence manifest is written last as the completion
marker; a failed check never produces that marker.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


PRODUCT = "farm_enterprise_economics"
REQUIRED = (
    "calculator.py", "guided_start.py", "test_calculator.py", "test_guided_start.py",
    "README.md", "CUSTOMER_GUIDE.md", "example_inputs.json",
    "build_technical_evidence.py",
)
TEST_MODULES = ("test_calculator.py", "test_guided_start.py")
CRITERION_TESTS = {
    "Q035": ("test_mississippi_state_extension_2020_greenhouse_enterprise_budget",
             "test_portfolio_aggregation_without_double_fixed_costs"),
    "Q036": ("test_mississippi_state_extension_2020_greenhouse_enterprise_budget",),
    "Q037": ("test_continuous_break_even_quantity_for_fractional_crop_sales",
             "test_negative_contribution_has_no_break_even",
             "test_extreme_negative_decimal_exponents_are_bounded"),
    "Q061": ("test_break_even_and_totals", "test_real_cli_json_and_csv",
             "test_success_creates_four_consistent_reports_and_original_inputs"),
    "Q063": ("test_invalid_extremes_fail_with_input_error",
             "test_three_factor_input_cost_stress_matches_explicit_farm_economics",
             "test_three_factor_cost_stress_does_not_double_count_shared_fixed_costs",
             "test_invalid_numbers_and_duplicate_names_are_reprompted",
             "test_confirmation_is_fail_closed_and_creates_no_files"),
    "Q064": ("test_cli_verification_recalculates_and_rejects_tampering_without_writes",
             "test_cli_stages_all_formats_before_replacing_any_existing_report",
             "test_each_export_goes_to_new_folder_without_overwrite",
             "test_output_parent_symlink_is_rejected_before_any_writes",
             "test_end_of_input_is_safe_cancellation"),
}
EXPORTS = {"baseline.json": "--json-output", "scenarios.csv": "--csv-output",
           "joint-stress.csv": "--three-factor-csv-output", "management-report.html": "--html-output"}


def sha256(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def execute(argv, cwd):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(argv, cwd=str(cwd), env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, universal_newlines=True,
                            timeout=120, check=False)
    if result.returncode:
        raise ValueError("PRODUCT_EVIDENCE_EXECUTION_FAILED:" + Path(argv[0]).name)
    return result.stdout + result.stderr


def build(recipe_dir, evidence_dir):
    recipe = Path(recipe_dir)
    target = Path(evidence_dir)
    if recipe.is_symlink() or target.is_symlink():
        raise ValueError("PRODUCT_EVIDENCE_PATH_UNSAFE")
    recipe = recipe.resolve(strict=True)
    if not recipe.is_dir() or not all((recipe / name).is_file() and not (recipe / name).is_symlink()
                                       for name in REQUIRED):
        raise ValueError("PRODUCT_RECIPE_FILES_MISSING")
    test_names = []
    for module in TEST_MODULES:
        tests = ast.parse((recipe / module).read_text(encoding="utf-8"))
        test_names.extend(node.name for node in ast.walk(tests)
                          if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                          and node.name.startswith("test_"))
    test_names.sort()
    if len(test_names) < 39 or len(set(test_names)) != len(test_names):
        raise ValueError("PRODUCT_TEST_COVERAGE_INCOMPLETE")
    if any(name not in test_names for names in CRITERION_TESTS.values() for name in names):
        raise ValueError("PRODUCT_CRITERION_TEST_MISSING")

    readme = (recipe / "README.md").read_text(encoding="utf-8").lower()
    if not all(note in readme for note in ("not estimated probabilities", "before depreciation",
                                              "illustrative", "guided_start.py", "customer_guide.md")):
        raise ValueError("PRODUCT_LIMITATIONS_UNDOCUMENTED")
    source_hashes = {name: sha256(recipe / name) for name in REQUIRED}
    if target.is_symlink():
        raise ValueError("PRODUCT_EVIDENCE_DESTINATION_NOT_EMPTY")
    # Atomic creation also rejects concurrent writers targeting one receipt.
    try:
        target.mkdir(mode=0o700)
    except FileExistsError:
        raise ValueError("PRODUCT_EVIDENCE_DESTINATION_NOT_EMPTY") from None
    with tempfile.TemporaryDirectory(prefix=".f01-evidence-", dir=str(target)) as ephemeral:
        stage = Path(ephemeral)
        test_log = execute([sys.executable, "-B", "-m", "unittest", "-q", *TEST_MODULES], recipe)
        ran = re.search(r"Ran (\d+) tests? in", test_log)
        if (not ran or int(ran.group(1)) != len(test_names)
                or not re.search(r"(?m)^OK\s*$", test_log)
                or re.search(r"\bskipped=|\bexpected failures=|\bunexpected successes=", test_log)):
            raise ValueError("PRODUCT_TEST_SUITE_NOT_FULLY_PASSED")

        export_command = [sys.executable, "-B", "calculator.py", "example_inputs.json"]
        for filename, flag in EXPORTS.items():
            export_command.extend((flag, str(stage / filename)))
        execute(export_command, recipe)
        for filename in EXPORTS:
            path = stage / filename
            if not path.is_file() or not path.stat().st_size:
                raise ValueError("PRODUCT_REPORT_NOT_GENERATED:" + filename)
        report = json.loads((stage / "baseline.json").read_text(encoding="utf-8"))
        if (not report.get("results") or report.get("input_values_independently_validated") is not False
                or report.get("accounting_scope") != "contribution_profit_before_depreciation_financing_tax"):
            raise ValueError("PRODUCT_REPORT_SCOPE_INVALID")
        if any(sha256(recipe / name) != value for name, value in source_hashes.items()):
            raise ValueError("PRODUCT_SOURCE_CHANGED_DURING_EVIDENCE_CAPTURE")
        (stage / "test_execution.log").write_text(test_log, encoding="utf-8")

        created_at = datetime.now(timezone.utc).isoformat()
        receipts = {}
        for criterion, selected_tests in CRITERION_TESTS.items():
            evidence = {
                "schema": "saeit.factory.f01-internal-evidence.v1",
                "product_id": PRODUCT, "criterion_id": criterion,
                "evidence_class": "internally_reproduced_technical_check",
                "independent_specialist_verified": False,
                "professionally_validated_quality_points": None,
                "selected_passing_tests": list(selected_tests),
                "complete_suite_passing_test_count": len(test_names),
                "product_source_sha256": source_hashes,
                "run_log_sha256": sha256(stage / "test_execution.log"),
                "generated_at_utc": created_at,
                "real_customer_data_used": False,
                "commercial_release_allowed": False,
            }
            filename = "evidence-" + criterion + ".json"
            (stage / filename).write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            receipts[criterion] = {"path": filename, "sha256": sha256(stage / filename)}
        manifest = {
            "schema": "saeit.factory.f01-technical-evidence-manifest.v1",
            "product_id": PRODUCT,
            "source_sha256": source_hashes,
            "test_count": len(test_names),
            "test_log_sha256": sha256(stage / "test_execution.log"),
            "exports_sha256": {name: sha256(stage / name) for name in EXPORTS},
            "candidate_criteria": receipts,
            "verified_quality_score": None,
            "independent_reviewer_approval": False,
            "receiver_acceptance": False,
            "commercial_release_allowed": False,
            "generated_at_utc": created_at,
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if target.is_symlink() or any((target / name).is_symlink() for name in
                                      (*EXPORTS, "test_execution.log", "manifest.json",
                                       *("evidence-" + id + ".json" for id in CRITERION_TESTS))):
            raise ValueError("PRODUCT_EVIDENCE_DESTINATION_UNSAFE")
        # Previous complete manifest remains until each new evidence file is ready.
        for filename in (*EXPORTS, "test_execution.log", *("evidence-" + id + ".json" for id in CRITERION_TESTS)):
            os.replace(str(stage / filename), str(target / filename))
            os.chmod(str(target / filename), 0o600)
        os.replace(str(stage / "manifest.json"), str(target / "manifest.json"))
        os.chmod(str(target / "manifest.json"), 0o600)
        return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe-dir", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--evidence-dir", required=True)
    args = parser.parse_args()
    value = build(args.recipe_dir, args.evidence_dir)
    print("F01_PRODUCT_BOUND_TECHNICAL_EVIDENCE=PASS")
    print("F01_TESTS_PASSED=" + str(value["test_count"]))
    print("F01_INTERNAL_EVIDENCE_CRITERIA=" + str(len(value["candidate_criteria"])))
    print("F01_INDEPENDENT_QC1000=HOLD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
