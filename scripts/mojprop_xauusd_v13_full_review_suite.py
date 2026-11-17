#!/usr/bin/env python3
"""Run *every* nonproduction Moj Prop XAUUSD v1.3 unit test explicitly.

Local/manual only. This file does NOT modify GitHub Actions, create payment
requests, interact with a broker, deploy code, or write to customer databases.

Run at repository root:
    python -B scripts/mojprop_xauusd_v13_full_review_suite.py

A successful exit proves only these exact tests passed IN THAT environment.
It never approves a new legal contract, 30 TRX settlement or live orders.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

# Exact source test counts, checked against the repository on 2026-11-17.
REQUIRED_TEST_MODULES = (
    ("tests.test_xauusd_v13_preflight", 28),
    ("tests.test_xauusd_v13_broker_evidence", 31),
    ("tests.test_xauusd_v13_contract_gate", 14),
    ("tests.test_xauusd_v13_draft_terms", 27),
    ("tests.test_xauusd_v13_qualification_preview", 32),
    ("tests.test_xauusd_v13_cross_source_guard", 12),
    ("tests.test_xauusd_v13_phase_day_audit", 20),
)
LEGACY_TEST_MODULE = "tests.test_prop_firm_policy"
EXPECTED_V13_TESTS = 164


def run_full_review() -> int:
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    loader = unittest.TestLoader()
    all_tests = unittest.TestSuite()
    observed = {}
    for module, expected in REQUIRED_TEST_MODULES:
        suite = loader.loadTestsFromName(module)
        observed[module] = suite.countTestCases()
        if loader.errors or observed[module] != expected:
            print(json.dumps({
                "status": "BLOCKED_MISSING_OR_DRIFTED_TESTS",
                "module": module, "expected": expected,
                "observed": observed[module],
                "loader_errors": loader.errors,
                "live_orders_authorized": False,
                "checkout_authorized": False,
            }, ensure_ascii=False), file=sys.stderr)
            return 2
        all_tests.addTests(suite)
    if sum(observed.values()) != EXPECTED_V13_TESTS:
        print("Unexpected v1.3 test count; fail closed", file=sys.stderr)
        return 2
    historical = loader.loadTestsFromName(LEGACY_TEST_MODULE)
    if loader.errors or historical.countTestCases() == 0:
        print("Legacy contract regression suite absent; fail closed", file=sys.stderr)
        return 2
    all_tests.addTests(historical)
    result = unittest.TextTestRunner(verbosity=2).run(all_tests)
    print(json.dumps({
        "status": "UNIT_TESTS_PASS_NOT_RELEASE" if result.wasSuccessful() else "UNIT_TESTS_FAIL",
        "v13_expected_test_cases": EXPECTED_V13_TESTS,
        "v13_test_modules": observed,
        "total_unit_tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "legacy_contract_suite_included": True,
        "live_orders_authorized": False,
        "checkout_authorized": False,
        "customer_enrollment_authorized": False,
        "independent_broker_and_funding_verified": False,
    }, ensure_ascii=False, sort_keys=True))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(run_full_review())
