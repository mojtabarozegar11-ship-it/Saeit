"""Internal staff-panel contract for MOJ PROP reservation preparation.

This is deliberately not a Django URL or a broker adapter. It gives the
existing authenticated staff panel a typed, fail-closed service boundary:
read-only exposure is available to staff, while reservation preparation stays
disabled until an explicitly reviewed feature flag and server-side risk
provider are present. Browser JSON never supplies risk facts or permissions.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .plan1_execution_boundary import (
    BoundaryResult,
    OwnerAccountExecutionBoundary,
)
from .plan1_owner_reservations import Exposure
from .plan1_shared_owner_risk import RiskPreview

_ALLOWED_REF = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"


class PanelContractError(Exception):
    """Base class for staff-panel contract failures."""


class PanelAccessDenied(PanelContractError):
    """The caller is not an authenticated staff actor."""


class PanelReservationDisabled(PanelContractError):
    """The reservation preparation flag is not enabled."""


@dataclass(frozen=True)
class PanelReservationRequest:
    actor_user_id: int
    account_ref: str
    trader_ref: str
    reservation_id: str
    idempotency_key: str
    order_ref: str
    proposed_margin_usd: Decimal

    def validate(self) -> None:
        if (type(self.actor_user_id) is not int
                or self.actor_user_id <= 0):
            raise ValueError("positive authenticated actor id required")
        import re
        for value, label in (
            (self.account_ref, "account reference"),
            (self.trader_ref, "trader reference"),
            (self.reservation_id, "reservation id"),
            (self.idempotency_key, "idempotency key"),
            (self.order_ref, "order reference"),
        ):
            if type(value) is not str or re.fullmatch(_ALLOWED_REF, value) is None:
                raise ValueError(f"invalid {label}")


class StaffPanelReservationContract:
    """Safe service used by a future staff-panel view."""

    def __init__(
        self, boundary: OwnerAccountExecutionBoundary,
        *, reservation_prepare_enabled: bool = False,
    ):
        self.boundary = boundary
        self.reservation_prepare_enabled = reservation_prepare_enabled

    def _require_staff(self, actor_is_staff: bool) -> None:
        if actor_is_staff is not True:
            raise PanelAccessDenied("authenticated staff actor required")

    def read_exposure(
        self, *, actor_is_staff: bool, account_ref: str,
        trader_ref: str | None = None,
    ) -> Exposure:
        self._require_staff(actor_is_staff)
        return self.boundary.ledger.exposure(account_ref, trader_ref)

    def prepare_reservation(
        self, *, actor_is_staff: bool, request: PanelReservationRequest,
        review: RiskPreview,
    ) -> BoundaryResult:
        self._require_staff(actor_is_staff)
        if self.reservation_prepare_enabled is not True:
            raise PanelReservationDisabled(
                "panel reservation preparation is disabled"
            )
        request.validate()
        return self.boundary.reserve_reviewed_order(
            review=review,
            reservation_id=request.reservation_id,
            idempotency_key=request.idempotency_key,
            account_ref=request.account_ref,
            trader_ref=request.trader_ref,
            proposed_margin_usd=request.proposed_margin_usd,
            order_ref=request.order_ref,
        )
