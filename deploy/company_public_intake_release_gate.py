#!/usr/bin/env python3
"""Conservative commercialization readiness gate from public GET metadata.

This does NOT authorize a live release; it only locates missing structural
signals and lists independent host evidence still required. CI test success
and public HTTP 200 never turn into approval for a payment/customer cutover.
"""
from __future__ import annotations

import json
import sys

PREFIX = "ZM_PUBLIC_INTAKE_READONLY="
EXPECTED_TARGETS = frozenset(("canonical_php", "company_page", "contact_page"))
REQUIRED_PUBLIC = (
    "public_html_observed",
    "same_origin_https",
)


def evaluate_report(report):
    if not isinstance(report, dict) or report.get("mode") != "public_readonly_get_no_credentials":
        raise ValueError("invalid_public_probe_contract")
    observations = report.get("results")
    if not isinstance(observations, list) or len(observations) != 3:
        raise ValueError("invalid_public_probe_results")
    by_name = {}
    for row in observations:
        if not isinstance(row, dict) or row.get("target") in by_name:
            raise ValueError("invalid_probe_row")
        name = row.get("target")
        if name not in EXPECTED_TARGETS:
            raise ValueError("unknown_probe_target")
        by_name[name] = row
    if set(by_name) != EXPECTED_TARGETS:
        raise ValueError("missing_probe_target")

    form = by_name["canonical_php"]
    issues = []
    if form.get("observation") != "public_html_observed" or form.get("http_status") != 200:
        issues.append("php_public_html_not_observed")
    if form.get("structural_evidence_complete") is not True:
        issues.append("php_public_form_evidence_incomplete")
    if form.get("candidate_post_email_form_count_capped", 0) < 1:
        issues.append("no_post_with_email_form_observed")
    target = form.get("submission_target_class")
    if target not in ("same_origin_default", "same_origin_https"):
        issues.append("post_destination_unverified_or_cross_origin")
    if form.get("submit_control_in_candidate") is not True:
        issues.append("submit_control_not_observed")
    if form.get("consent_named_in_candidate") is not True:
        issues.append("named_consent_field_not_observed")
    if form.get("required_named_consent_checkbox_seen") is not True:
        issues.append("required_named_consent_checkbox_not_observed")
    if form.get("csrf_named_hidden_in_candidate") is not True:
        issues.append("csrf_named_hidden_field_not_observed")
    if form.get("captcha_named_field_in_candidate") is not True:
        issues.append("captcha_named_field_not_observed")

    for page in ("company_page", "contact_page"):
        if by_name[page].get("http_status") != 200:
            issues.append(page + "_public_http_200_not_observed")

    # These cannot be certified by any public GET or isolated test, and must
    # remain blockers even if every visible front-end structure is present.
    unverified = (
        "php_server_side_consent_validation_and_retention",
        "php_post_persistence_and_spam_controls",
        "live_cpanel_database_mapping_and_recovery",
        "real_buyers_delivered_to_unified_management_desk",
        "authorized_price_payment_fulfillment_and_receipt",
    )
    return {
        "readiness": "NO_GO_REQUIRES_PRODUCTION_HOST_EVIDENCE",
        "source": "public_get_only_not_host_audit",
        "public_structural_findings": sorted(issues),
        "production_unverified_requirements": list(unverified),
        "public_php_post_email_form_observed": (
            form.get("candidate_post_email_form_count_capped", 0) >= 1
        ),
        "public_php_same_origin_https_action_observed": target in (
            "same_origin_default", "same_origin_https"
        ),
        "real_customer_post_submitted": False,
        "cash_settlement_verified": None,
        "release_authorized": False,
    }


def main(path):
    try:
        # Reading only the local redacted probe JSON line. Never ingest
        # external URL, environment secrets, a page body or private form data.
        with open(path, encoding="utf-8") as handle:
            line = handle.read(24576).strip()
        if not line.startswith(PREFIX):
            raise ValueError("missing_expected_prefix")
        report = json.loads(line[len(PREFIX):])
        result = evaluate_report(report)
    except (ValueError, TypeError, KeyError, OSError, json.JSONDecodeError):
        result = {
            "readiness": "NO_GO_PROBE_INVALID_OR_UNAVAILABLE",
            "public_structural_findings": ["unverifiable_public_probe"],
            "production_unverified_requirements": ["complete_manual_host_audit"],
            "real_customer_post_submitted": False,
            "cash_settlement_verified": None,
            "release_authorized": False,
        }
    print("ZM_PUBLIC_INTAKE_RELEASE_GATE=" + json.dumps(result, sort_keys=True))
    # No run of this tool is authorized to merge, deploy, send or take payment.
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: company_public_intake_release_gate.py LOCAL_PROBE_JSONLINE")
    raise SystemExit(main(sys.argv[1]))
