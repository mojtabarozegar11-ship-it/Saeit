"""Read-only LiteFinance demo evidence contract.

No HTTP client, credential, order sender or live-account authority exists in
this module. It validates the shape and attribution of evidence that a future
owner-authenticated demo adapter may provide. Every switch is disabled by
default; validated evidence is not itself execution permission.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import re


_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_SOURCE = "litefinance-demo-read-only"
_STATUSES = frozenset(("filled", "closed", "cancelled"))


class DemoContractError(Exception):
    """Base class for demo evidence contract failures."""


class DemoAdapterDisabled(DemoContractError):
    """No live/demo broker adapter is connected."""


class DemoEvidenceRejected(DemoContractError):
    """Evidence is incomplete, mismatched or not independently bounded."""


@dataclass(frozen=True)
class DemoAccountSnapshot:
    broker_account_ref: str
    owner_account_ref: str
    equity_usd: Decimal
    free_margin_usd: Decimal
    observed_at: str
    source: str
    evidence_digest: str


@dataclass(frozen=True)
class DemoExecutionReport:
    broker_account_ref: str
    broker_order_ref: str
    reservation_id: str
    trader_ref: str
    status: str
    observed_at: str
    source: str
    evidence_digest: str


def _ref(value: str, label: str) -> str:
    if type(value) is not str or _REF.fullmatch(value) is None:
        raise DemoEvidenceRejected(f"invalid {label}")
    return value


def _amount(value: Decimal, label: str) -> Decimal:
    if (type(value) is not Decimal or not value.is_finite()
            or value < 0 or value.as_tuple().exponent < -8):
        raise DemoEvidenceRejected(f"invalid {label}")
    return value


def _digest(value: str) -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise DemoEvidenceRejected("sha256 evidence digest required")
    return value


class LiteFinanceDemoEvidenceContract:
    """Validate read-only demo evidence; never submit an order."""

    def __init__(self, *, expected_broker_account_ref: str,
                 read_adapter_enabled: bool = False):
        self.expected_broker_account_ref = _ref(
            expected_broker_account_ref, "expected broker account reference"
        )
        self.read_adapter_enabled = read_adapter_enabled

    def _require_read_adapter(self) -> None:
        if self.read_adapter_enabled is not True:
            raise DemoAdapterDisabled(
                "LiteFinance adapter is not connected or enabled"
            )

    def validate_snapshot(self, snapshot: DemoAccountSnapshot) -> DemoAccountSnapshot:
        self._require_read_adapter()
        if type(snapshot) is not DemoAccountSnapshot:
            raise TypeError("exact DemoAccountSnapshot required")
        if _ref(snapshot.broker_account_ref, "broker account reference") != self.expected_broker_account_ref:
            raise DemoEvidenceRejected("broker account attribution mismatch")
        _ref(snapshot.owner_account_ref, "owner account reference")
        _amount(snapshot.equity_usd, "equity")
        _amount(snapshot.free_margin_usd, "free margin")
        if type(snapshot.observed_at) is not str or not snapshot.observed_at.strip():
            raise DemoEvidenceRejected("observation timestamp required")
        if snapshot.source != _SOURCE:
            raise DemoEvidenceRejected("unapproved evidence source")
        _digest(snapshot.evidence_digest)
        return snapshot

    def validate_execution_report(
        self, report: DemoExecutionReport, *, expected_reservation_id: str,
        expected_trader_ref: str,
    ) -> DemoExecutionReport:
        self._require_read_adapter()
        if type(report) is not DemoExecutionReport:
            raise TypeError("exact DemoExecutionReport required")
        if _ref(report.broker_account_ref, "broker account reference") != self.expected_broker_account_ref:
            raise DemoEvidenceRejected("broker account attribution mismatch")
        if _ref(report.broker_order_ref, "broker order reference") == "":
            raise DemoEvidenceRejected("broker order reference required")
        if _ref(report.reservation_id, "reservation id") != _ref(
            expected_reservation_id, "expected reservation id"
        ):
            raise DemoEvidenceRejected("reservation attribution mismatch")
        if _ref(report.trader_ref, "trader reference") != _ref(
            expected_trader_ref, "expected trader reference"
        ):
            raise DemoEvidenceRejected("trader attribution mismatch")
        if report.status not in _STATUSES:
            raise DemoEvidenceRejected("unsupported demo execution status")
        if type(report.observed_at) is not str or not report.observed_at.strip():
            raise DemoEvidenceRejected("execution observation timestamp required")
        if report.source != _SOURCE:
            raise DemoEvidenceRejected("unapproved evidence source")
        _digest(report.evidence_digest)
        return report

    def submit_order(self, *_args, **_kwargs) -> None:
        raise DemoAdapterDisabled(
            "no broker order submission exists in the demo contract"
        )
