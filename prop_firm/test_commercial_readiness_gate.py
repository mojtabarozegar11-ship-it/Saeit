from .commercial_readiness_gate import (
    CommercialReleaseClosed,
    REQUIRED_GATES,
    evaluate_commercial_readiness,
)


def complete_gates():
    return {name: True for name in REQUIRED_GATES}


class TestCommercialReadiness:
    def test_current_closed_controls_never_become_release(self):
        result = evaluate_commercial_readiness(
            gates=complete_gates(),
            public_route_enabled=False,
            payment_enabled=False,
        )
        assert result.eligible_for_release is False
        assert result.disabled_controls == (
            "public_route_enabled",
            "payment_enabled",
        )
        assert result.invoice_created is False
        assert result.settlement_allowed is False

    def test_missing_contract_and_reconciliation_gates_block(self):
        gates = complete_gates()
        gates["product_contract_finalized"] = False
        gates["payment_reconciliation_verified"] = False
        result = evaluate_commercial_readiness(
            gates=gates,
            public_route_enabled=True,
            payment_enabled=True,
        )
        assert result.eligible_for_release is False
        assert result.missing_gates == (
            "product_contract_finalized",
            "payment_reconciliation_verified",
        )

    def test_only_complete_evidence_and_explicit_controls_are_eligible(self):
        result = evaluate_commercial_readiness(
            gates=complete_gates(),
            public_route_enabled=True,
            payment_enabled=True,
        )
        assert result.eligible_for_release is True

    def test_untrusted_gate_values_are_rejected(self):
        gates = complete_gates()
        gates["kyc_and_age_provider_ready"] = 1
        try:
            evaluate_commercial_readiness(
                gates=gates,
                public_route_enabled=False,
                payment_enabled=False,
            )
        except CommercialReleaseClosed:
            pass
        else:
            raise AssertionError("integer gate must be rejected")

    def test_module_has_no_side_effect_markers(self):
        source = open(
            __file__.replace(
                "test_commercial_readiness_gate.py",
                "commercial_readiness_gate.py",
            ),
            encoding="utf-8",
        ).read()
        for forbidden in (
            "create_invoice",
            "broadcast",
            "payout",
            "place_order",
            "send_mail",
            "enable_payment",
        ):
            assert forbidden not in source
