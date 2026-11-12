"""Broker-result evidence checks, not fabricated trading or earnings."""
from datetime import datetime, timezone
from pathlib import Path
import os

import pytest

from trading.mojtrade_demo_receipt_reconcile import (
    DemoAuditError, reconcile_file, reconcile_text,
)


SESSION = "0123456789abcdef0123456789abcdef"
STAMP_A = "2026-11-10T11:00:00.0000000Z"
STAMP_B = "2026-11-10T11:01:00.0000000Z"
START = (
    "MOJTRADE_AUDIT_V1|START|session=" + SESSION
    + "|alias=LITE_DEMO_1|currency=USD|symbol=XAUUSD|mode=demo|count=2"
)
A = (
    "MOJTRADE_AUDIT_V1|DEAL|session=" + SESSION
    + "|deal_id=2026123456|position_id=32145|closed_utc=" + STAMP_A
    + "|side=buy|lots=0.01|gross=12|commission=-1|swap=-0.5"
    + "|net=10.5|balance_after=10010.5"
)
B = (
    "MOJTRADE_AUDIT_V1|DEAL|session=" + SESSION
    + "|deal_id=2026123457|position_id=32146|closed_utc=" + STAMP_B
    + "|side=sell|lots=0.02|gross=-7|commission=-1|swap=-0.2"
    + "|net=-8.2|balance_after=10002.3"
)
END = (
    "MOJTRADE_AUDIT_V1|END|session=" + SESSION
    + "|count=2|wins=1|gross=5|commission=-2|swap=-0.7|net=2.3"
    + "|demo_only=true|external_broker_reconciliation=false"
)
NOW = datetime(2026, 11, 12, tzinfo=timezone.utc)


def valid_log(*, prefix=""):
    return "\n".join(prefix + line for line in (START, A, B, END)) + "\n"


def parse(data):
    return reconcile_text(data, now=NOW)


def test_valid_demo_receipt_preserves_native_broker_net_and_separate_fees():
    result = parse(valid_log())
    assert result["closing_deal_count"] == 2
    assert result["distinct_closing_deals"] == 2
    assert result["mode"] == "demo"
    assert result["alias"] == "LITE_DEMO_1"
    assert result["account_currency"] == "USD"
    assert result["wins"] == 1 and result["losses"] == 1
    assert result["gross_account_currency"] == "5"
    assert result["commissions_account_currency"] == "-2"
    assert result["swaps_account_currency"] == "-0.7"
    assert result["broker_reported_net_account_currency"] == "2.3"
    assert result["realized_demo_trade_profit_factor"] is not None
    assert result["real_account_revenue_verified"] is False
    assert result["profits_are_demo_only_not_withdrawable"] is True
    assert result["source_log_is_independently_authenticated"] is False
    assert result["broker_statement_reconciled"] is False
    assert result["complete_account_transaction_ledger_reconciled"] is False
    assert result["real_account_trades"] == 0
    assert result["broker_order_placement_enabled"] is False
    assert len(result["unique_deal_ids_sha256"]) == 64


def test_identical_log_is_deterministic_and_handles_ctrader_prefix():
    a = parse(valid_log(prefix="2026-11-12 22:20:00 Info :: "))
    b = parse(valid_log(prefix="2026-11-12 22:20:00 Info :: "))
    assert a == b


@pytest.mark.parametrize("modified", [
    valid_log().replace("count=2", "count=3", 1),
    valid_log().replace("|wins=1", "|wins=2"),
    valid_log().replace("|net=2.3", "|net=99.3"),
    valid_log().replace("|gross=5", "|gross=6"),
    valid_log().replace("|commission=-2", "|commission=-200"),
    valid_log().replace("|swap=-0.7", "|swap=-7.7"),
    valid_log().replace("|mode=demo", "|mode=live"),
    valid_log().replace("|demo_only=true", "|demo_only=false"),
    valid_log().replace("external_broker_reconciliation=false", "external_broker_reconciliation=true"),
    valid_log().replace("|net=10.5", "|net=NaN"),
    valid_log().replace("|lots=0.01", "|lots=0"),
    valid_log().replace("|lots=0.01", "|lots=-1"),
    valid_log().replace("|deal_id=2026123457", "|deal_id=2026123456"),
    valid_log().replace("|closed_utc=" + STAMP_A, "|closed_utc=2099-11-10T11:00:00.0000000Z"),
    valid_log().replace("|alias=LITE_DEMO_1", "|alias=demo|cash=1000"),
    valid_log().replace("|gross=12", "|gross=1e999"),
    valid_log().replace("|side=buy", "|side=buy_now"),
    valid_log().replace("|session=" + SESSION, "|session=" + "f"*32, 1),
    valid_log().replace("|currency=USD", "|currency=GBP|secret=123"),
    valid_log().replace("|symbol=XAUUSD", "|symbol="),
    valid_log().replace("|position_id=32145", "|position_id=0"),
    valid_log().replace("|position_id=32145", "|position_id=-1"),
    valid_log().replace("|commission=-1", "|commission=-1|commission=-1", 1),
    valid_log().replace("|net=-8.2", "|net=-8.2|unexpected=true"),
    valid_log().replace("|closed_utc=" + STAMP_B, "|closed_utc=2026-11-09T11:01:00.0000000Z"),
    valid_log().replace("MOJTRADE_AUDIT_V1|END", "MOJTRADE_AUDIT_V1|BLOCKED"),
    valid_log().rsplit("\n", 2)[0],
    valid_log().replace(A + "\n", A + "\n" + A + "\n"),
])
def test_forged_incomplete_mixed_or_duplicate_proofs_are_refused(modified):
    with pytest.raises(DemoAuditError):
        parse(modified)


def test_zero_trades_do_not_become_profit():
    document = (
        START.replace("count=2", "count=0")
        + "\n"
        + END.replace("count=2", "count=0").replace("wins=1", "wins=0")
           .replace("gross=5", "gross=0").replace("commission=-2", "commission=0")
           .replace("swap=-0.7", "swap=0").replace("net=2.3", "net=0")
        + "\n"
    )
    report = parse(document)
    assert report["closing_deal_count"] == 0
    assert report["win_rate"] is None
    assert report["realized_demo_trade_profit_factor"] is None
    assert report["broker_reported_net_account_currency"] == "0"
    assert report["real_account_revenue_verified"] is False


def test_private_evidence_is_sha256_bound_and_rejects_world_readable(tmp_path):
    evidence = tmp_path / "private-audit.log"
    evidence.write_text(valid_log(), encoding="utf-8")
    os.chmod(evidence, 0o600)
    result = reconcile_file(evidence)
    assert len(result["source_log_sha256"]) == 64
    os.chmod(evidence, 0o644)
    with pytest.raises(DemoAuditError, match="private_log_permissions_too_open"):
        reconcile_file(evidence)


def test_private_evidence_symlink_is_rejected(tmp_path):
    evidence = tmp_path / "audit.log"
    evidence.write_text(valid_log(), encoding="utf-8")
    target = tmp_path / "link.log"
    target.symlink_to(evidence)
    with pytest.raises(DemoAuditError, match="private_log_path_invalid"):
        reconcile_file(target)


def test_native_audit_robot_is_demo_only_and_never_submits_orders():
    source = (Path(__file__).resolve().parents[1] / "trading"
              / "MojTradeDemoHistoryAuditBot.cs").read_text()
    assert "if (Account.IsLive)" in source
    assert "History.FindAll(TradeLabel, SymbolName)" in source
    assert "NetProfit.ToString" in source
    assert "ClosingDealId" in source
    assert "AccessRights.None" in source
    assert "broker_reconciliation=true" not in source
    for forbidden in ("ExecuteMarketOrder(", "PlaceLimitOrder(", "PlaceStopOrder(",
                      "ModifyPosition(", "ClosePosition(", "Withdraw(", "HttpClient("):
        assert forbidden not in source
