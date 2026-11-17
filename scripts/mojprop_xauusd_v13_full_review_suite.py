#!/usr/bin/env python3
"""Run every nonproduction MOJ PROP XAUUSD v1.3 and social v1.4 unit test.

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
    ("tests.test_xauusd_v13_social_evidence", 30),
    ("tests.test_plan1_v14_social_or_28d", 34),
    ("tests.test_plan1_v14_combined_qualification", 17),
    ("tests.test_plan1_v14_private_interest_review", 30),
    ("tests.test_plan1_v141_precontract_boundary", 33),
    ("tests.test_mojprop_v141_prelaunch_copy", 30),
    ("tests.test_mojprop_v141_info_url_source", 20),
    ("tests.test_mojprop_v141_private_portfolio_source", 20),
    ("tests.test_plan1_v141_simulated_challenge_engine", 73),
    ("tests.test_plan1_v141_demo_order_risk_review", 28),
    ("tests.test_plan1_v141_signed_simulator_manifest", 40),
    ("tests.test_plan1_v141_replay_journal_policy", 74),
    ("tests.test_plan1_v141_django_journal_source", 32),
    ("tests.test_plan1_v141_mariadb_readonly_preflight", 35),
    ("tests.test_plan1_v141_shared_company_master_review", 30),
    ("tests.test_plan1_v141_virtual_tenant_fill_ledger", 67),
    ("tests.test_plan1_v141_virtual_tenant_django_source", 39),
)
LEGACY_TEST_MODULE = "tests.test_prop_firm_policy"
EXPECTED_V13_TESTS = 194
EXPECTED_V14_TESTS = 602
EXPECTED_ALL_TESTS = EXPECTED_V13_TESTS + EXPECTED_V14_TESTS


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
    v13_modules = {name: count for name, count in observed.items()
                   if name.startswith("tests.test_xauusd_v13_")}
    v14_modules = {name: count for name, count in observed.items()
                   if name.startswith("tests.test_plan1_v14")
                   or name in ("tests.test_mojprop_v141_prelaunch_copy",
                               "tests.test_mojprop_v141_info_url_source",
                               "tests.test_mojprop_v141_private_portfolio_source")}
    if (sum(v13_modules.values()) != EXPECTED_V13_TESTS
            or sum(v14_modules.values()) != EXPECTED_V14_TESTS):
        print("Version-specific unit test inventory drift; fail closed", file=sys.stderr)
        return 2
    if sum(observed.values()) != EXPECTED_ALL_TESTS:
        print("Unexpected v1.3/v1.4.1 combined test count; fail closed", file=sys.stderr)
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
        "v14_expected_test_cases": EXPECTED_V14_TESTS,
        "combined_v13_v14_expected_test_cases": EXPECTED_ALL_TESTS,
        "v13_test_modules": v13_modules,
        "v14_test_modules": v14_modules,
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
