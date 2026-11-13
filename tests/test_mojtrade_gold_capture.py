"""Contract tests for one-bot cTrader demo gold capture, never live fills."""
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
from contextlib import nullcontext
from io import StringIO
import json
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from core.models import AgentTask

import pytest

from core.mojtrade_gold_capture import (
    GoldCaptureError, MARKER, ROWS, capture_to_snapshot, preview_private_gold_capture,
)


NOW = datetime(2026, 11, 13, 12, 30, tzinfo=timezone.utc)
SESSION = "a" * 32


def _stamp(utc):
    return utc.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.0000000Z")


def _repack(lines):
    body = "\n".join(lines[:-1])
    digest = hashlib.sha256(body.encode("ascii")).hexdigest()
    end = lines[-1].split("|")
    end[-1] = digest
    lines[-1] = "|".join(end)
    return ("\n".join(lines) + "\n").encode("ascii")


def sample_capture(*, now=NOW):
    generated = now - timedelta(seconds=10)
    first = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=80)
    header = "|".join((
        MARKER, "START", SESSION, "LITE_DEMO_1", _stamp(generated),
        "2008.00", "2008.11", "0.01", "0.01", "10000", "8000", "-20",
        "10", "0", "0", str(ROWS),
    ))
    lines = [header]
    for idx in range(ROWS):
        price = 2000 + idx / 10
        lines.append("|".join((
            MARKER, "BAR", SESSION, _stamp(first + timedelta(hours=idx)),
            f"{price:.4f}", f"{price+0.2:.4f}",
            f"{price-0.2:.4f}", f"{price+0.1:.4f}",
        )))
    lines.append("|".join((MARKER, "END", SESSION, str(ROWS), "0"*64)))
    return _repack(lines)


def test_sample_capture_gives_full_80_candle_input_with_no_execution():
    snapshot = capture_to_snapshot(sample_capture(), now=NOW)
    assert snapshot["owner"] == "mojtaba-bot-ai"
    assert snapshot["symbol"] == "XAUUSD"
    assert snapshot["timeframe"] == "H1"
    assert snapshot["account_mode"] == "demo"
    assert snapshot["account_alias"] == "LITE_DEMO_1"
    assert snapshot["quote"]["bid"] == "2008.00"
    assert snapshot["quote"]["ask"] == "2008.11"
    assert len(snapshot["candles"]) == 80
    assert snapshot["account_risk"]["realized_daily_pnl"] == "-20"
    assert snapshot["account_risk"]["open_stop_risk"] == "10"
    assert snapshot["account_risk"]["pending_orders"] == 0


@pytest.fixture
def private_capture(tmp_path):
    root = tmp_path / "trusted"
    root.mkdir(mode=0o700)
    path = root / "gold-demo.log"
    path.write_bytes(sample_capture())
    path.chmod(0o600)
    return path


def test_private_end_to_end_preview_keeps_prices_nonexecutable(private_capture):
    report = preview_private_gold_capture(private_capture, now=NOW)
    assert report["owner"] == "mojtaba-bot-ai"
    assert report["source_kind"] == "unverified_local_ctrader_demo_log"
    assert report["source_authenticated_by_broker"] is False
    assert report["broker_data_independently_authenticated"] is False
    assert report["orders"] == 0
    assert report["order_intent"] is None
    assert report["publication_authorized"] is False
    assert report["trade_execution_authorized"] is False
    assert report["real_revenue_verified"] is False
    assert len(report["capture_log_sha256"]) == 64
    assert report["capture_log_sha256"] == hashlib.sha256(
        private_capture.read_bytes()
    ).hexdigest()


@pytest.mark.parametrize("mutation", [
    "truncated", "missing_end", "extra_bar", "missing_bar",
    "tampered_candle", "tampered_header", "wrong_count", "wrong_session",
    "duplicate_bar", "new_session_midstream", "missing_marker",
    "crlf_unexpected", "non_ascii", "oversized",
])
def test_invalid_or_tampered_capture_fails_closed(mutation):
    data = sample_capture()
    lines = data.decode("ascii").strip().split("\n")
    if mutation == "truncated":
        data = data[:300]
    elif mutation == "missing_end":
        data = "\n".join(lines[:-1]).encode("ascii")
    elif mutation == "extra_bar":
        data = "\n".join(lines[:-1] + [lines[-2], lines[-1]]).encode("ascii")
    elif mutation == "missing_bar":
        data = "\n".join(lines[:-2] + [lines[-1]]).encode("ascii")
    elif mutation == "tampered_candle":
        data = data.replace(b"2000.1000", b"2000.2000", 1)
    elif mutation == "tampered_header":
        data = data.replace(b"2008.11", b"2008.21", 1)
    elif mutation == "wrong_count":
        x = lines[0].split("|")
        x[-1] = "79"
        lines[0] = "|".join(x)
        data = _repack(lines)
    elif mutation == "wrong_session":
        x = lines[-1].split("|")
        x[2] = "b"*32
        lines[-1] = "|".join(x)
        data = _repack(lines)
    elif mutation == "duplicate_bar":
        lines[50] = lines[49]
        data = _repack(lines)
    elif mutation == "new_session_midstream":
        lines[2] = lines[2].replace(SESSION, "b"*32)
        data = _repack(lines)
    elif mutation == "missing_marker":
        lines[5] = lines[5].replace(MARKER, "FAKE_MARKER")
        data = _repack(lines)
    elif mutation == "crlf_unexpected":
        data = data.replace(b"\n", b"\r\n")
    elif mutation == "non_ascii":
        data = data + b"\xff"
    else:
        data = b"x" * 40_001
    with pytest.raises(GoldCaptureError):
        capture_to_snapshot(data, now=NOW)


@pytest.mark.parametrize("case", [
    "future", "expired", "wrong_alias", "negative_equity", "not_integer_count",
    "bad_quote", "invalid_ohlc", "missing_hour", "weekend_gap",
    "too_old_last_close", "pending_order", "exhausted_risk",
])
def test_repacked_unsafe_or_expired_capture_never_authorizes_signal(case, private_capture):
    lines = sample_capture().decode("ascii").strip().split("\n")
    head = lines[0].split("|")
    if case == "future":
        head[4] = _stamp(NOW + timedelta(seconds=1))
    elif case == "expired":
        head[4] = _stamp(NOW - timedelta(minutes=2))
    elif case == "wrong_alias":
        head[3] = "another/bot"
    elif case == "negative_equity":
        head[9] = "-10000"
    elif case == "not_integer_count":
        head[13] = "1.2"
    elif case == "bad_quote":
        head[6] = head[5]
    elif case == "pending_order":
        head[14] = "1"
    elif case == "exhausted_risk":
        head[11] = "-400"
    lines[0] = "|".join(head)
    if case in ("invalid_ohlc", "missing_hour", "weekend_gap", "too_old_last_close"):
        row = lines[40].split("|")
        if case == "invalid_ohlc":
            row[6] = "9000"
        elif case == "missing_hour":
            row[3] = _stamp(NOW - timedelta(hours=13))
        elif case == "weekend_gap":
            row[3] = _stamp(NOW - timedelta(days=3, hours=10))
        else:
            for idx in range(1, ROWS + 1):
                parts = lines[idx].split("|")
                parts[3] = _stamp(
                    datetime.fromisoformat(parts[3].replace("Z", "+00:00"))
                    - timedelta(days=3)
                )
                lines[idx] = "|".join(parts)
        lines[40] = "|".join(row)
    private_capture.write_bytes(_repack(lines))
    with pytest.raises(GoldCaptureError) if case not in ("pending_order", "exhausted_risk") else nullcontext():
        report = preview_private_gold_capture(private_capture, now=NOW)
        if case in ("pending_order", "exhausted_risk"):
            assert report["levels"] is None
            assert report["trade_execution_authorized"] is False


@pytest.mark.parametrize("failure", [
    "world_directory", "world_file", "symlink", "hardlink", "missing", "relative",
])
def test_private_log_file_safety_blocks_unsafe_paths(private_capture, tmp_path, failure):
    source = private_capture
    if failure == "world_directory":
        source.parent.chmod(0o755)
    elif failure == "world_file":
        source.chmod(0o644)
    elif failure == "symlink":
        target = source.with_name("real.log")
        source.rename(target)
        source.symlink_to(target)
    elif failure == "hardlink":
        clone = source.with_name("hardlink.log")
        clone.hardlink_to(source)
    elif failure == "missing":
        source.unlink()
    else:
        source = Path("relative.log")
    with pytest.raises(GoldCaptureError):
        preview_private_gold_capture(source, now=NOW)



@pytest.mark.django_db
def test_owner_private_capture_management_command_never_creates_order_task(
    private_capture,
):
    output = StringIO()
    original = preview_private_gold_capture
    with patch(
        "core.management.commands.mojtrade_gold_capture_preview.preview_private_gold_capture",
        side_effect=lambda path: original(path, now=NOW),
    ):
        call_command("mojtrade_gold_capture_preview",
                     "--input", str(private_capture), stdout=output)
    report = json.loads(output.getvalue())
    assert report["source_kind"] == "unverified_local_ctrader_demo_log"
    assert report["source_authenticated_by_broker"] is False
    assert report["trade_execution_authorized"] is False
    assert report["publication_authorized"] is False
    assert report["orders"] == 0
    assert report["order_intent"] is None
    assert not AgentTask.objects.exists()


@pytest.mark.django_db
def test_owner_private_capture_command_blocks_world_readable_evidence(private_capture):
    private_capture.chmod(0o644)
    with pytest.raises(CommandError, match="MOJTABA_GOLD_CAPTURE_BLOCKED"):
        call_command("mojtrade_gold_capture_preview",
                     "--input", str(private_capture), stdout=StringIO())
    assert not AgentTask.objects.exists()
