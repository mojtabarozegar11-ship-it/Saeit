"""Bounded, thread-safe pending ledger for non-financial signal orders.

This is an application-boundary contract, NOT a durable database or payment
processor. It cannot be exposed as a live order store until a transactionally
durable adapter with a unique tenant/order index is installed.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from threading import RLock
import re

try:
    from .mojtaba_signal_order_contract import (
        SignalOrderContractError, SignalOrderIntent, build_pending_order_record,
    )
except ImportError as exc:
    if __package__:
        raise
    from mojtaba_signal_order_contract import (
        SignalOrderContractError, SignalOrderIntent, build_pending_order_record,
    )


class SignalLedgerError(ValueError):
    """Raised when a pending ledger operation is unsafe or inconsistent."""


_ORDER_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
_MAX_BATCH_SIZE = 500
_MAX_PENDING = 100000


@dataclass(frozen=True)
class PendingOrderReceipt:
    order_id: str
    created: bool
    record: dict


class PendingSignalOrderLedger:
    """In-memory rehearsal, with atomic intake and strict capacity limits."""

    def __init__(self, *, max_records=10000):
        if type(max_records) is not int or not 1 <= max_records <= _MAX_PENDING:
            raise SignalLedgerError("ledger_capacity_invalid")
        self._max_records = max_records
        self._records = {}
        self._lock = RLock()

    def record(self, intent: SignalOrderIntent, route, offer, *, now=None):
        candidate = build_pending_order_record(intent, route, offer, now=now)
        order_id = candidate["order_id"]
        with self._lock:
            existing = self._records.get(order_id)
            if existing is not None:
                if existing != candidate:
                    raise SignalLedgerError("order_id_conflict")
                return PendingOrderReceipt(
                    order_id=order_id, created=False, record=deepcopy(existing),
                )
            if len(self._records) >= self._max_records:
                raise SignalLedgerError("ledger_capacity_reached")
            self._records[order_id] = deepcopy(candidate)
            return PendingOrderReceipt(
                order_id=order_id, created=True, record=deepcopy(candidate),
            )

    def record_batch(self, rows, *, now=None) -> tuple[PendingOrderReceipt, ...]:
        """Validate all and insert all or none; no partial customer imports."""
        if type(rows) not in (list, tuple):
            raise SignalLedgerError("order_batch_required")
        if len(rows) > _MAX_BATCH_SIZE:
            raise SignalLedgerError("order_batch_too_large")
        incoming = {}
        order_ids = []
        for row in rows:
            if type(row) not in (tuple, list) or len(row) != 3:
                raise SignalLedgerError("order_batch_row_invalid")
            candidate = build_pending_order_record(
                row[0], row[1], row[2], now=now,
            )
            order_id = candidate["order_id"]
            if order_id in incoming:
                raise SignalLedgerError("duplicate_order_id_in_batch")
            incoming[order_id] = candidate
            order_ids.append(order_id)
        with self._lock:
            for order_id in order_ids:
                existing = self._records.get(order_id)
                if existing is not None and existing != incoming[order_id]:
                    raise SignalLedgerError("order_id_conflict")
            new_orders = sum(order_id not in self._records for order_id in order_ids)
            if len(self._records) + new_orders > self._max_records:
                raise SignalLedgerError("ledger_capacity_reached")
            receipts = []
            for order_id in order_ids:
                created = order_id not in self._records
                if created:
                    self._records[order_id] = deepcopy(incoming[order_id])
                receipts.append(PendingOrderReceipt(
                    order_id=order_id, created=created,
                    record=deepcopy(self._records[order_id]),
                ))
            return tuple(receipts)

    def get(self, order_id: str):
        if type(order_id) is not str or not _ORDER_ID.fullmatch(order_id):
            raise SignalLedgerError("order_id_required")
        with self._lock:
            record = self._records.get(order_id)
            return None if record is None else deepcopy(record)

    def snapshot(self) -> tuple[dict, ...]:
        with self._lock:
            return tuple(deepcopy(self._records[key]) for key in sorted(self._records))

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)
