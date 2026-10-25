"""Indexer observations are untrusted candidate TxIDs, not receipts."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from services.mpw_trx_walletless_core import InvoiceIntent, PaymentHold
from services.mpw_crown_trx_discovery import discover_native_candidates
from services.mpw_tron_independent_solidified_rpc import hex_to_tron_address

RECEIVER_HEX = "41" + "11" * 20
OTHER_HEX = "41" + "33" * 20
RECEIVER = hex_to_tron_address(RECEIVER_HEX)
TX = "a" * 64


def _invoice():
    now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    return InvoiceIntent(
        order_id=12, customer_id=5, network="tron-mainnet",
        recipient=RECEIVER, amount_sun=19960000,
        usd_total=Decimal("4.99"), quote_usd_per_trx=Decimal("0.25"),
        issued_at=now, expires_at=now + timedelta(minutes=10),
    )


def _indexed(*, amount=19960000, to=RECEIVER_HEX, tx=TX, timestamp=None):
    now = _invoice().issued_at + timedelta(seconds=30)
    return {
        "txID": tx,
        "block_timestamp": timestamp if timestamp is not None else int(now.timestamp() * 1000),
        "raw_data": {"contract": [{
            "type": "TransferContract",
            "parameter": {"value": {
                "to_address": to, "amount": amount,
                "owner_address": OTHER_HEX,
            }},
        }]},
    }


def test_exact_indexer_candidate_is_just_a_txid():
    inp = _invoice()
    docs = {"data": [_indexed()], "meta": {}}
    actual = discover_native_candidates(inp, "test-indexer-key-for-tests",
                                        transport=lambda _: docs)
    assert actual == [TX]


@pytest.mark.parametrize("wrong", [
    {"amount": 19959999}, {"to": OTHER_HEX},
    {"tx": "not-a-txid"},
    {"timestamp": int((_invoice().issued_at - timedelta(minutes=1)).timestamp()*1000)},
])
def test_indexer_wrong_amount_destination_time_hash_is_ignored(wrong):
    docs = {"data": [_indexed(**wrong)], "meta": {}}
    assert discover_native_candidates(
        _invoice(), "test-indexer-key-for-tests", transport=lambda _: docs,
    ) == []


def test_no_unauthenticated_indexer_access():
    with pytest.raises(PaymentHold):
        discover_native_candidates(_invoice(), "", transport=lambda _: {})


def test_malformed_and_overbroad_results_fail_closed():
    with pytest.raises(PaymentHold):
        discover_native_candidates(
            _invoice(), "test-indexer-key-for-tests",
            transport=lambda _: {"data": "not a list"},
        )
