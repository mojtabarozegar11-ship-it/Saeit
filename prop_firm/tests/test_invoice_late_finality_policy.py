"""Contract regression for late-finalized transfers, without RPC or money movement."""
from datetime import datetime, timedelta, timezone
import pytest

from prop_firm.invoice_expiry_policy import (
    InvoiceExpiredOrInvalid,
    require_finalized_transfer_in_invoice_window,
    require_unexpired_invoice,
)

START = datetime(2026, 11, 23, 12, tzinfo=timezone.utc)
END = START + timedelta(hours=24)


def test_in_window_transfer_can_finalize_after_expiry():
    require_finalized_transfer_in_invoice_window(
        issued_at=START, expires_at=END,
        transfer_block_time=END - timedelta(seconds=1),
        status="expired", now=END + timedelta(hours=2),
    )


@pytest.mark.parametrize("block_time", [START - timedelta(seconds=1), END, END + timedelta(seconds=1)])
def test_out_of_window_transfer_is_rejected(block_time):
    with pytest.raises(InvoiceExpiredOrInvalid):
        require_finalized_transfer_in_invoice_window(
            issued_at=START, expires_at=END, transfer_block_time=block_time,
            status="awaiting", now=END + timedelta(hours=2),
        )


def test_future_block_timestamp_rejected():
    with pytest.raises(InvoiceExpiredOrInvalid):
        require_finalized_transfer_in_invoice_window(
            issued_at=START, expires_at=END, transfer_block_time=START + timedelta(hours=1),
            status="awaiting", now=START,
        )


def test_pre_invoice_expiry_remains_closed():
    with pytest.raises(InvoiceExpiredOrInvalid):
        require_unexpired_invoice(issued_at=START, expires_at=END, status="awaiting", now=END)


@pytest.mark.parametrize("status", ["paid", "void", "refunded", ""])
def test_non_pending_status_rejected(status):
    with pytest.raises(InvoiceExpiredOrInvalid):
        require_finalized_transfer_in_invoice_window(
            issued_at=START, expires_at=END, transfer_block_time=START,
            status=status, now=END,
        )
