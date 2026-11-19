"""Tests for the fail-closed staff panel reservation contract."""
from decimal import Decimal as D
import os
import tempfile
import unittest

from prop_firm.plan1_execution_boundary import OwnerAccountExecutionBoundary
from prop_firm.plan1_owner_reservations import ReservationLedger
from prop_firm.plan1_panel_reservation_contract import (
    PanelAccessDenied, PanelReservationDisabled, PanelReservationRequest,
    StaffPanelReservationContract,
)
from prop_firm.plan1_shared_owner_risk import RiskPreview


class PanelContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(prefix="mojprop-panel-", delete=False)
        self.tmp.close()
        self.ledger = ReservationLedger(self.tmp.name)
        self.boundary = OwnerAccountExecutionBoundary(self.ledger)
        self.disabled = StaffPanelReservationContract(self.boundary)
        self.enabled = StaffPanelReservationContract(
            self.boundary, reservation_prepare_enabled=True
        )
        self.review = RiskPreview(
            review_allowed=True, reasons=(), allocated_capital_usd=D("200"),
            aggregate_open_and_reserved_risk_usd=D("0"),
            proposed_order_risk_usd=D("0.80"),
            trader_order_limit_usd=D("0.80"),
            trader_aggregate_limit_usd=D("1.60"),
            account_aggregate_limit_usd=D("3.20"),
        )
        self.request = PanelReservationRequest(
            actor_user_id=1, account_ref="OWNER-LIVE", trader_ref="TRADER-A",
            reservation_id="RES-001", idempotency_key="IDEM-001",
            order_ref="ORDER-001", proposed_margin_usd=D("10"),
        )

    def tearDown(self):
        self.ledger.close()
        os.unlink(self.tmp.name)

    def test_default_preparation_is_disabled(self):
        with self.assertRaises(PanelReservationDisabled):
            self.disabled.prepare_reservation(
                actor_is_staff=True, request=self.request, review=self.review
            )

    def test_nonstaff_cannot_read_exposure(self):
        with self.assertRaises(PanelAccessDenied):
            self.disabled.read_exposure(
                actor_is_staff=False, account_ref="OWNER-LIVE"
            )

    def test_nonstaff_cannot_prepare_reservation(self):
        with self.assertRaises(PanelAccessDenied):
            self.enabled.prepare_reservation(
                actor_is_staff=False, request=self.request, review=self.review
            )

    def test_staff_can_read_empty_exposure(self):
        exposure = self.disabled.read_exposure(
            actor_is_staff=True, account_ref="OWNER-LIVE"
        )
        self.assertEqual(exposure.reservation_count, 0)
        self.assertEqual(exposure.reserved_risk_usd, D("0"))

    def test_enabled_contract_prepares_only_internal_reservation(self):
        result = self.enabled.prepare_reservation(
            actor_is_staff=True, request=self.request, review=self.review
        )
        self.assertEqual(result.reservation.status, "reserved")
        self.assertFalse(result.execution_submitted)

    def test_panel_request_requires_positive_actor(self):
        with self.assertRaises(ValueError):
            PanelReservationRequest(
                **{**self.request.__dict__, "actor_user_id": 0}
            ).validate()

    def test_panel_request_rejects_invalid_account_reference(self):
        with self.assertRaises(ValueError):
            PanelReservationRequest(
                **{**self.request.__dict__, "account_ref": "OWNER / LIVE"}
            ).validate()

    def test_panel_request_rejects_invalid_order_reference(self):
        with self.assertRaises(ValueError):
            PanelReservationRequest(
                **{**self.request.__dict__, "order_ref": "order with spaces"}
            ).validate()

    def test_panel_request_rejects_non_decimal_margin_at_ledger(self):
        request = PanelReservationRequest(
            **{**self.request.__dict__, "proposed_margin_usd": 10.0}
        )
        with self.assertRaises(ValueError):
            self.enabled.prepare_reservation(
                actor_is_staff=True, request=request, review=self.review
            )

    def test_panel_request_rejects_review_denial(self):
        denied = RiskPreview(
            review_allowed=False, reasons=("risk_limit",),
            allocated_capital_usd=D("200"),
            aggregate_open_and_reserved_risk_usd=D("0"),
            proposed_order_risk_usd=D("0.80"),
            trader_order_limit_usd=D("0.80"),
            trader_aggregate_limit_usd=D("1.60"),
            account_aggregate_limit_usd=D("3.20"),
        )
        with self.assertRaises(Exception):
            self.enabled.prepare_reservation(
                actor_is_staff=True, request=self.request, review=denied
            )

    def test_panel_retry_is_idempotent(self):
        first = self.enabled.prepare_reservation(
            actor_is_staff=True, request=self.request, review=self.review
        )
        second = self.enabled.prepare_reservation(
            actor_is_staff=True, request=self.request, review=self.review
        )
        self.assertEqual(first, second)

    def test_panel_read_exposure_sees_reservation(self):
        self.enabled.prepare_reservation(
            actor_is_staff=True, request=self.request, review=self.review
        )
        exposure = self.disabled.read_exposure(
            actor_is_staff=True, account_ref="OWNER-LIVE", trader_ref="TRADER-A"
        )
        self.assertEqual(exposure.reserved_risk_usd, D("0.80"))

    def test_panel_never_submits(self):
        result = self.enabled.prepare_reservation(
            actor_is_staff=True, request=self.request, review=self.review
        )
        self.assertFalse(result.execution_submitted)
        self.assertIsNone(result.reservation.broker_order_ref)

    def test_panel_does_not_accept_customer_deposit(self):
        self.assertNotIn(
            "customer_deposit",
            StaffPanelReservationContract.prepare_reservation.__code__.co_varnames,
        )

    def test_panel_does_not_accept_browser_risk_facts(self):
        self.assertNotIn(
            "proposed_order_risk_usd",
            StaffPanelReservationContract.prepare_reservation.__code__.co_varnames,
        )

    def test_read_exposure_is_available_when_prepare_is_disabled(self):
        self.assertEqual(
            self.disabled.read_exposure(
                actor_is_staff=True, account_ref="OWNER-LIVE"
            ).reserved_capital_usd,
            D("0"),
        )

    def test_request_fields_are_immutable(self):
        with self.assertRaises(Exception):
            self.request.actor_user_id = 2

    def test_invalid_review_type_is_rejected_by_boundary(self):
        with self.assertRaises(TypeError):
            self.enabled.prepare_reservation(
                actor_is_staff=True, request=self.request, review=True
            )


if __name__ == "__main__":
    unittest.main()
