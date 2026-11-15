"""Side-effect-free pending ledger for non-financial signal orders.

This is an application-boundary contract, not a database adapter. It records
only validated pending intents in memory, supports idempotent replay and
rejects conflicting reuse of an order ID. It never settles payment, grants
entitlement, publishes a signal or executes a trade.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

try:
    from .mojtaba_signal_order_contract import (
        SignalOrderContractError,
        SignalOrderIntent,
        build_pending_order_record,
    )
except ImportError as exc:
    if __package__:
        raise
    from mojtaba_signal_order_contract import (
        SignalOrderContractError,
        SignalOrderIntent,
        build_pending_order_record,
    )


class SignalLedgerError(ValueError):
    """Raised when a pending ledger operation is unsafe or inconsistent."""


@dataclass(frozen=True)
class PendingOrderReceipt:
    order_id: str
    created: bool
    record: dict


class PendingSignalOrderLedger:
    """In-memory pending boundary; persistence belongs to an approved adapter."""

    def __init__(self):
        self._records = {}

    def record(
        self,
        intent: SignalOrderIntent,
        route,
        offer,
        *,
        now=None,
    ) -> PendingOrderReceipt:
        try:
            candidate = build_pending_order_record(
                intent, route, offer, now=now
            )
        except SignalOrderContractError:
            raise
        order_id = candidate["order_id"]
        existing = self._records.get(order_id)
        if existing is not None:
            if existing != candidate:
                raise SignalLedgerError("order_id_conflict")
            return PendingOrderReceipt(
                order_id=order_id,
                created=False,
                record=deepcopy(existing),
            )
        self._records[order_id] = deepcopy(candidate)
        return PendingOrderReceipt(
            order_id=order_id,
            created=True,
            record=deepcopy(candidate),
        )

    def get(self, order_id: str):
        if type(order_id) is not str or not order_id:
            raise SignalLedgerError("order_id_required")
        record = self._records.get(order_id)
        return None if record is None else deepcopy(record)

    def snapshot(self) -> tuple[dict, ...]:
        return tuple(
            deepcopy(self._records[key])
            for key in sorted(self._records)
        )

    def __len__(self) -> int:
        return len(self._records)
