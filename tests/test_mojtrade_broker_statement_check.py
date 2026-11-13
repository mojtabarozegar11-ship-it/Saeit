"""Regressions for cTrader demo log vs normalized statement, not real P&L."""
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os

import pytest

from trading.mojtrade_broker_statement_check import (
    FIELDS, StatementCrosscheckError, compare_bytes, compare_private_files,
)


SESSION = "0123456789abcdef0123456789abcdef"
NOW = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)
BOT_ROWS = [
    {
        "deal_id": "2026123456", "position_id": "32145",
        "closed_utc": "2026-11-10T11:00:00.0000000Z",
        "symbol": "XAUUSD", "label": "MojTrade-OMEGA-X-DEMO",
        "side": "buy", "lots": "0.01", "gross": "12",
        "commission": "-1", "swap": "-0.5", "net": "10.5",
        "balance_after": "10010.5", "currency": "USD",
    },
    {
        "deal_id": "2026123457", "position_id": "32146",
        "closed_utc": "2026-11-10T11:01:00.0000000Z",
        "symbol": "XAUUSD", "label": "MojTrade-OMEGA-X-DEMO",
        "side": "sell", "lots": "0.02", "gross": "-7",
        "commission": "-1", "swap": "-0.2", "net": "-8.2",
        "balance_after": "10002.3", "currency": "USD",
    },
]
START = (
    "MOJTRADE_AUDIT_V1|START|session=" + SESSION +
    "|alias=LITE_DEMO_1|currency=USD|symbol=XAUUSD|mode=demo|count=2"
)
END = (
    "MOJTRADE_AUDIT_V1|END|session=" + SESSION +
    "|count=2|wins=1|gross=5|commission=-2|swap=-0.7|net=2.3"
    "|demo_only=true|external_broker_reconciliation=false"
)


def log_bytes():
    deals = []
    for row in BOT_ROWS:
        keys = ("deal_id", "position_id", "closed_utc", "side", "lots",
                "gross", "commission", "swap", "net", "balance_after")
        deals.append("MOJTRADE_AUDIT_V1|DEAL|session=" + SESSION
                     + "".join("|" + key + "=" + row[key] for key in keys))
    return ("\n".join([START, *deals, END]) + "\n").encode()


def csv_bytes(rows=None, *, fields=FIELDS):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=list(fields))
    writer.writeheader()
    for row in BOT_ROWS if rows is None else rows:
        writer.writerow({key: row.get(key, "") for key in fields})
    return out.getvalue().encode()


def manifest_bytes(csv_data, **changes):
    base = {
        "schema_version": 1, "broker": "LiteFinance",
        "account_mode": "demo", "account_alias": "LITE_DEMO_1",
        "account_currency": "USD", "symbol": "XAUUSD",
        "source": "ctrader_history_statement_export",
        "full_label_history": True,
        "statement_sha256": hashlib.sha256(csv_data).hexdigest(),
        "exported_at_utc": "2026-11-11T12:00:00Z",
    }
    base.update(changes)
    return json.dumps(base, sort_keys=True).encode()


def check(rows=None, **manifest_changes):
    csv_data = csv_bytes(rows)
    return compare_bytes(log_bytes(), csv_data, manifest_bytes(csv_data, **manifest_changes))


def test_two_complete_demo_exports_match_by_deal_not_by_aggregate():
    result = check()
    assert result["matched_closing_deals"] == 2
    assert result["missing_or_extra_deals"] == 0
    assert result["statement_net_demo_only"] == "2.3"
    assert result["bot_log_net_demo_only"] == "2.3"
    assert result["two_exports_matched_within_money_tolerance"] is True
    assert result["source_cryptographically_authenticated_to_broker"] is False
    assert result["exports_independent_of_broker_platform"] is False
    assert result["separate_authenticated_account_statement_verified"] is False
    assert result["deposit_withdrawal_conversion_reconciled"] is False
    assert result["real_income_verified"] is False
    assert result["live_order_execution_enabled"] is False
    assert len(result["log_sha256"]) == 64
    assert len(result["statement_sha256"]) == 64
    assert len(result["statement_manifest_sha256"]) == 64
    assert check() == result


@pytest.mark.parametrize(("key", "value"), [
    ("deal_id", "2026123499"), ("position_id", "987654"),
    ("closed_utc", "2026-11-10T12:01:00.0000000Z"),
    ("symbol", "XAGUSD"), ("label", "another-bot"),
    ("side", "buy"), ("lots", "0.03"), ("gross", "-8"),
    ("commission", "-2"), ("swap", "-2"), ("net", "-9"),
    ("balance_after", "10003.3"), ("currency", "EUR"),
])
def test_wrong_per_deal_fields_are_not_hidden_by_aggregate_totals(key, value):
    modified = [dict(x) for x in BOT_ROWS]
    modified[1][key] = value
    with pytest.raises(StatementCrosscheckError):
        check(modified)


@pytest.mark.parametrize("scope", [
    {"broker": "OtherBroker"},
    {"account_mode": "live"},
    {"account_alias": "OTHER_DEMO"},
    {"account_currency": "EUR"},
    {"symbol": "BTCUSD"},
    {"source": "screenshot"},
    {"full_label_history": False},
    {"statement_sha256": "0" * 64},
    {"exported_at_utc": "2100-11-11T12:00:00Z"},
    {"exported_at_utc": "2026-11-11T12:00:00"},
    {"schema_version": True},
])
def test_wrong_broker_account_scope_source_or_manifest_is_rejected(scope):
    with pytest.raises(StatementCrosscheckError):
        check(**scope)


def test_truncated_duplicates_and_extra_deals_all_rejected():
    for rows in (
        BOT_ROWS[:1],
        [BOT_ROWS[0], BOT_ROWS[0]],
        BOT_ROWS + [dict(BOT_ROWS[1], deal_id="2026123499")],
    ):
        with pytest.raises(StatementCrosscheckError):
            check(rows)


def test_wrong_columns_not_accepted_as_raw_ctrader_export():
    raw = csv_bytes(fields=tuple(x for x in FIELDS if x != "net"))
    with pytest.raises(StatementCrosscheckError, match="statement_columns_not_normalized"):
        compare_bytes(log_bytes(), raw, manifest_bytes(raw))


def test_normalized_statement_is_not_third_party_proof_and_two_files_are_private(tmp_path):
    log = tmp_path / "audit.log"
    statement = tmp_path / "ctrader-statement-normalized.csv"
    manifest = tmp_path / "ctrader-statement-manifest.json"
    log.write_bytes(log_bytes())
    statement.write_bytes(csv_bytes())
    manifest.write_bytes(manifest_bytes(statement.read_bytes()))
    for path in (log, statement, manifest):
        os.chmod(path, 0o600)
    assert compare_private_files(log, statement, manifest)["matched_closing_deals"] == 2
    os.chmod(statement, 0o644)
    with pytest.raises(StatementCrosscheckError, match="private_source_permissions_insecure"):
        compare_private_files(log, statement, manifest)


def test_file_symlinks_and_wrong_manifest_hash_refused(tmp_path):
    log = tmp_path / "audit.log"
    statement = tmp_path / "statement.csv"
    manifest = tmp_path / "manifest.json"
    log.write_bytes(log_bytes())
    statement.write_bytes(csv_bytes())
    manifest.write_bytes(manifest_bytes(statement.read_bytes()))
    for path in (log, statement, manifest):
        os.chmod(path, 0o600)
    linked = tmp_path / "linked-audit.log"
    linked.symlink_to(log)
    with pytest.raises(StatementCrosscheckError, match="private_source_path_invalid"):
        compare_private_files(linked, statement, manifest)
    statement.write_bytes(statement.read_bytes() + b"\n")
    with pytest.raises(StatementCrosscheckError, match="statement_manifest_identity_or_scope_mismatch"):
        compare_private_files(log, statement, manifest)


def test_import_never_places_orders_or_claims_cash_profits():
    import pathlib
    source = (pathlib.Path(__file__).resolve().parents[1] /
              "trading" / "mojtrade_broker_statement_check.py").read_text()
    for forbidden in ("ExecuteMarketOrder(", "PlaceLimitOrder(", "withdraw(", "requests.post(", "HttpClient("):
        assert forbidden not in source
