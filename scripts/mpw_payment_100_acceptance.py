#!/usr/bin/env python3
"""Fail-closed 100/100 acceptance of MojPlayWin payment ONLY.

An authorized assessor's signed manifest is necessary but not sufficient:
an independent human must first validate all private real-payment evidence.
No network access, financial writes, gateway activation or secrets in output.
"""
import argparse
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import sys

CASES = (
    "mobile_desktop_visuals",
    "accessibility_localization",
    "transparent_amount_network_fees",
    "guest_purchase",
    "direct_trx_checkout",
    "crypto_asset_network_coverage",
    "invoice_and_wallet_security",
    "finality_reconciliation",
    "recovery_and_operations",
    "real_paid_delivery",
)
VALID_SOURCES = {
    "visual_human_and_browser",
    "accessibility_human_and_automation",
    "provider_quote_integration",
    "browser_guest_e2e",
    "tron_chain_independent",
    "independent_crypto_mainnet_routes",
    "security_review",
    "provider_and_chain_reconciliation",
    "fault_injection_live_safe",
    "private_real_transaction_e2e",
}
SOURCES = dict(zip(CASES, (
    "visual_human_and_browser",
    "accessibility_human_and_automation",
    "provider_quote_integration",
    "browser_guest_e2e",
    "tron_chain_independent",
    "independent_crypto_mainnet_routes",
    "security_review",
    "provider_and_chain_reconciliation",
    "fault_injection_live_safe",
    "private_real_transaction_e2e",
)))
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def payload_to_sign(manifest):
    return json.dumps(
        {key: value for key, value in manifest.items() if key != "hmac_sha256"},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def _date(text):
    if not isinstance(text, str) or not text.endswith("Z"):
        raise ValueError("Timestamp must be UTC ISO-8601 with Z")
    return dt.datetime.fromisoformat(text[:-1] + "+00:00")


def evaluate(manifest, secret, *, now=None):
    """Returns (accepted, safe_public_details). Never prints raw private evidence."""
    reasons = []
    if not isinstance(manifest, dict):
        return False, {"status": "BLOCKED", "reason": "invalid_or_missing_attestation"}
    if not isinstance(secret, str) or len(secret) < 32:
        reasons.append("independent_attestation_key_unavailable")
    else:
        supplied = manifest.get("hmac_sha256", "")
        if not isinstance(supplied, str) or not HEX64.fullmatch(supplied):
            reasons.append("invalid_attestation_signature")
        else:
            expected = hmac.new(secret.encode(), payload_to_sign(manifest), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(supplied, expected):
                reasons.append("untrusted_attestation_signature")
    if manifest.get("policy_version") != "crypto-only-20261021":
        reasons.append("wrong_or_obsolete_fiat_gateway_policy")
    if manifest.get("payment_scope") != "cryptocurrency_only":
        reasons.append("not_scoped_to_crypto_only")
    if manifest.get("domain") != "mojplaywin.com" or manifest.get("environment") != "production":
        reasons.append("wrong_site_or_environment")
    if manifest.get("owner_signed_off") is not True:
        reasons.append("owner_acceptance_missing")
    if manifest.get("independent_assessor_signed_off") is not True:
        reasons.append("independent_review_missing")
    if manifest.get("real_payment_evidence_reviewed") is not True:
        reasons.append("real_payment_evidence_not_independently_reviewed")
    if manifest.get("critical_security_defects_present") is not False:
        reasons.append("critical_security_clearance_not_proven")
    if manifest.get("critical_financial_defects_present") is not False:
        reasons.append("critical_financial_clearance_not_proven")
    stamp = manifest.get("verified_at_utc")
    clock = now if now is not None else dt.datetime.now(dt.timezone.utc)
    try:
        time = _date(stamp)
        if time > clock or clock - time > dt.timedelta(days=7):
            reasons.append("stale_or_future_evidence")
    except (TypeError, ValueError):
        reasons.append("invalid_attestation_date")
    cases = manifest.get("checks")
    if not isinstance(cases, dict) or set(cases) != set(CASES):
        reasons.append("missing_or_unexpected_criteria")
        cases = cases if isinstance(cases, dict) else {}
    accepted_groups = []
    for case in CASES:
        item = cases.get(case)
        if (isinstance(item, dict)
            and item.get("passed") is True
            and item.get("points") == 10
            and type(item.get("points")) is int
            and item.get("source") == SOURCES[case]
            and isinstance(item.get("evidence_sha256"), str)
            and HEX64.fullmatch(item["evidence_sha256"])
        ):
            accepted_groups.append(case)
        else:
            reasons.append("unverified_" + case)
    accepted = not reasons and len(accepted_groups) == 10
    return accepted, {
        "scope": "mojplaywin.com/cryptocurrency_payment_gateway_only",
        "status": "ACCEPTED_100_OF_100" if accepted else "BLOCKED_NOT_100",
        "verified_gates_in_manifest": len(accepted_groups),
        "total_required_gates": 10,
        "reasons": reasons[:22],
        "note": "A valid signature authenticates a private review declaration; independent inspection of evidence is still mandatory.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", help="private signed acceptance manifest, never commit it")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        fake = {
            "policy_version": "crypto-only-20261021",
            "payment_scope": "cryptocurrency_only",
            "domain": "mojplaywin.com",
            "environment": "production",
            "verified_at_utc": "2026-10-21T00:00:00Z",
            "owner_signed_off": True,
            "independent_assessor_signed_off": True,
            "real_payment_evidence_reviewed": True,
            "critical_security_defects_present": False,
            "critical_financial_defects_present": False,
            "checks": {
                case: {"passed": True, "points": 10, "source": SOURCES[case], "evidence_sha256": "a" * 64}
                for case in CASES
            },
        }
        key = "contract-test-only-" * 3
        fake["hmac_sha256"] = hmac.new(key.encode(), payload_to_sign(fake), hashlib.sha256).hexdigest()
        now = dt.datetime(2026, 10, 21, 5, tzinfo=dt.timezone.utc)
        ok, _ = evaluate(fake, key, now=now)
        assert ok, "Synthetic fixture must exercise full contract (NOT real payment proof)"
        for case in CASES:
            broken = json.loads(json.dumps(fake))
            broken["checks"][case]["passed"] = False
            ok, _ = evaluate(broken, key, now=now)
            assert not ok, "Missing or forged criterion must fail closed"
        for field in ("owner_signed_off", "independent_assessor_signed_off", "real_payment_evidence_reviewed"):
            broken = json.loads(json.dumps(fake))
            broken[field] = False
            broken["hmac_sha256"] = hmac.new(key.encode(), payload_to_sign(broken), hashlib.sha256).hexdigest()
            ok, _ = evaluate(broken, key, now=now)
            assert not ok, field
        assert not evaluate(fake, "incorrect-key-xxxxxxxxxxxxxxxxxxxxxxxxx", now=now)[0]
        assert not evaluate(fake, "", now=now)[0]
        assert not evaluate(fake, key, now=dt.datetime(2026, 11, 2, tzinfo=dt.timezone.utc))[0]
        print("MPW_GATE_CONTRACT_SELFTEST=PASS; REAL_GATEWAY_ACCEPTANCE=NOT_ASSESSED")
        return 0
    manifest = None
    if args.evidence:
        try:
            with open(args.evidence, "r", encoding="utf-8") as stream:
                manifest = json.load(stream)
        except (OSError, ValueError):
            manifest = None
    ok, detail = evaluate(manifest, os.environ.get("MPW_PAYMENT_100_ATTESTATION_KEY"))
    print(json.dumps(detail, ensure_ascii=False, sort_keys=True))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
