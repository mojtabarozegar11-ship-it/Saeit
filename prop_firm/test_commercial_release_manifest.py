from .commercial_readiness_gate import CommercialReleaseClosed, REQUIRED_GATES
from .commercial_release_manifest import build_release_manifest


def evidence(status=True):
    return {
        name: {
            "status": status,
            "reference": f"ledger:{name}",
            "reviewed_at": "2026-11-20T00:00:00Z",
        }
        for name in REQUIRED_GATES
    }


def test_incomplete_evidence_reports_missing_gates_without_side_effects():
    manifest = build_release_manifest(
        evidence=evidence(False),
        public_route_enabled=False,
        payment_enabled=False,
    )
    assert manifest.readiness.eligible_for_release is False
    assert len(manifest.readiness.missing_gates) == len(REQUIRED_GATES)
    assert manifest.readiness.invoice_created is False
    assert manifest.readiness.settlement_allowed is False


def test_complete_gate_requires_reference_and_review_time():
    data = evidence(True)
    data["product_contract_finalized"]["reference"] = " "
    try:
        build_release_manifest(evidence=data)
    except CommercialReleaseClosed:
        pass
    else:
        raise AssertionError("complete gate without evidence reference must fail")


def test_unknown_gate_is_rejected():
    data = evidence(False)
    data["unexpected_gate"] = {
        "status": True,
        "reference": "ledger:unexpected",
        "reviewed_at": "2026-11-20T00:00:00Z",
    }
    try:
        build_release_manifest(evidence=data)
    except CommercialReleaseClosed:
        pass
    else:
        raise AssertionError("unknown gate must fail closed")


def test_complete_evidence_does_not_open_controls():
    manifest = build_release_manifest(
        evidence=evidence(True),
        public_route_enabled=False,
        payment_enabled=False,
    )
    assert manifest.readiness.missing_gates == ()
    assert manifest.readiness.disabled_controls == (
        "public_route_enabled",
        "payment_enabled",
    )
    assert manifest.readiness.eligible_for_release is False


def test_only_explicit_controls_make_manifest_eligible():
    manifest = build_release_manifest(
        evidence=evidence(True),
        public_route_enabled=True,
        payment_enabled=True,
    )
    assert manifest.readiness.eligible_for_release is True
