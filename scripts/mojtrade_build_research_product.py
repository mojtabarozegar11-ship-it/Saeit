#!/usr/bin/env python3
"""Build a private, versioned MojTrade research product artifact.

The artifact is evidence packaging only. It never publishes, sells, emails,
charges, settles funds, places orders, or represents trading profit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_SYMBOLS = ("BTC/USD", "ETH/USD")
ALLOWED_STANCES = frozenset({"watch_buy", "watch_sell", "neutral"})
# USD-quoted spot markets only. Binance BTCUSDT/ETHUSDT cannot be
# relabelled as BTC/USD or ETH/USD without breaking price provenance.
ALLOWED_SOURCES = frozenset({
    "coinbase-exchange-public-candles",
    "bitstamp-public-ohlc",
    "kraken-spot-public-ohlc",
    "bitfinex-public-candles",
})


class ProductArtifactError(ValueError):
    """Raised when a research report is not eligible for packaging."""


def _aware(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ProductArtifactError(f"{field}_missing_or_invalid")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ProductArtifactError(f"{field}_invalid") from exc
    if dt.tzinfo is None:
        raise ProductArtifactError(f"{field}_must_be_timezone_aware")
    return dt.astimezone(timezone.utc)


def build_artifact(report_path: Path, now: datetime | None = None) -> dict:
    if not report_path.is_absolute() or report_path.is_symlink():
        raise ProductArtifactError("report_path_must_be_private_absolute_file")
    if not report_path.is_file():
        raise ProductArtifactError("report_file_missing")
    if stat.S_IMODE(report_path.stat().st_mode) & 0o077:
        raise ProductArtifactError("report_file_permissions_too_open")
    try:
        raw = report_path.read_bytes()
        report = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProductArtifactError("report_unreadable") from exc
    if not isinstance(report, dict):
        raise ProductArtifactError("report_payload_not_object")
    if report.get("report_type") != "mojtrade-research-observation-consumption":
        raise ProductArtifactError("report_type_rejected")
    if report.get("action") != "research_only" or report.get("execution") != "disabled":
        raise ProductArtifactError("report_execution_boundary_rejected")
    if report.get("orders") != 0:
        raise ProductArtifactError("report_orders_must_be_zero")
    generated_at = _aware(report.get("generated_at"), "generated_at")
    expires_at = _aware(report.get("observation_expires_at"), "observation_expires_at")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if expires_at <= current or generated_at > current or expires_at <= generated_at:
        raise ProductArtifactError("report_time_window_invalid")
    signals = report.get("signals")
    if not isinstance(signals, list) or len(signals) != len(EXPECTED_SYMBOLS):
        raise ProductArtifactError("report_signal_count_invalid")
    normalized = []
    for signal, expected_symbol in zip(signals, EXPECTED_SYMBOLS):
        if not isinstance(signal, dict):
            raise ProductArtifactError("report_signal_invalid")
        if signal.get("symbol") != expected_symbol:
            raise ProductArtifactError("report_symbol_order_invalid")
        stance = signal.get("stance")
        source = signal.get("data_source")
        observed_at = _aware(signal.get("observed_at"), "observed_at")
        if stance not in ALLOWED_STANCES:
            raise ProductArtifactError("report_stance_invalid")
        if source not in ALLOWED_SOURCES:
            raise ProductArtifactError("report_provider_invalid")
        if observed_at > current or observed_at > expires_at:
            raise ProductArtifactError("report_signal_time_invalid")
        method = signal.get("method")
        if not isinstance(method, str) or not method.strip():
            raise ProductArtifactError("report_method_missing")
        normalized.append({
            "symbol": expected_symbol,
            "stance": stance,
            "observed_at": observed_at.isoformat(),
            "data_source": source,
            "method": method.strip(),
        })
    report_hash = hashlib.sha256(raw).hexdigest()
    return {
        "schema": "mojtrade.research-product-artifact.v1",
        "product_id": "mojtrade-hourly-market-research",
        "version": "1.0.0",
        "generated_at": current.replace(microsecond=0).isoformat(),
        "source_report_generated_at": generated_at.isoformat(),
        "source_report_expires_at": expires_at.isoformat(),
        "source_report_sha256": report_hash,
        "signals": normalized,
        "research_only": True,
        "execution": "disabled",
        "orders": 0,
        "publication_enabled": False,
        "delivery_enabled": False,
        "revenue_verified": False,
        "trading_pnl_included": False,
        "limitations": [
            "Not investment advice or a promise of profit.",
            "Research watch states are not verified profitable strategies.",
            "No execution, customer delivery, payment, or settlement is included.",
        ],
    }


def write_private(artifact: dict, destination: Path) -> None:
    if not destination.is_absolute() or destination.is_symlink():
        raise ProductArtifactError("artifact_destination_must_be_private_absolute_file")
    parent = destination.parent
    if not parent.is_dir() or parent.is_symlink() or stat.S_IMODE(parent.stat().st_mode) & 0o077:
        raise ProductArtifactError("artifact_directory_must_be_private_0700")
    data = (json.dumps(artifact, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=parent, prefix=".mojtrade-artifact-", delete=False) as handle:
            temporary = Path(handle.name)
            os.chmod(temporary, 0o600)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Package MojTrade research evidence privately")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        artifact = build_artifact(args.input)
        write_private(artifact, args.output)
    except (ProductArtifactError, OSError) as exc:
        parser.exit(2, f"MOJTRADE_ARTIFACT_REJECTED: {exc}\n")
    print("MOJTRADE_RESEARCH_ARTIFACT_WRITTEN: orders=0; delivery=disabled; revenue=unverified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
