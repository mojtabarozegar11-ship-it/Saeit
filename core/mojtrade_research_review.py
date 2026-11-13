"""Read-only, no-order MojTrade observation review for the ONE economic master bot.

No market fetch, prediction, broker connection, order, publication, wallet, or
revenue claim. A validated research observation is NOT an outcome/backtest.
"""
from __future__ import annotations

import hashlib
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.mojtrade_consume_observation import ObservationError, read_observation


MAX_SOURCE_BYTES = 96_000
MAX_OBSERVATION_WINDOW = timedelta(minutes=90)
MAX_CANDLE_AGE = timedelta(hours=3)
CANONICAL_SOURCE_RELATIVE = Path(
    "factory-runtime/private/mojtrade/validated-payload.json"
)


class ResearchReviewError(ValueError):
    """The private observation lacks adequate evidence or isolation."""


def trusted_source() -> Path:
    """Use the existing VPS observer's fixed file; never accept task input paths."""
    return Path.home() / CANONICAL_SOURCE_RELATIVE


def _capped_read(path: Path) -> bytes:
    with path.open("rb") as handle:
        data = handle.read(MAX_SOURCE_BYTES + 1)
    if not data or len(data) > MAX_SOURCE_BYTES:
        raise ResearchReviewError("MOJTRADE_PRIVATE_RESEARCH_SIZE_REJECTED")
    return data


def inspect_private_observation(path: Path, now: datetime | None = None) -> dict:
    """Review a source snapshot without writing any file or opening a socket."""
    if path != trusted_source() or path.is_symlink():
        raise ResearchReviewError("MOJTRADE_PRIVATE_RESEARCH_PATH_REJECTED")
    parent = path.parent
    if (
        parent.is_symlink() or parent.parent.is_symlink()
        or not parent.is_dir() or stat.S_IMODE(parent.stat().st_mode) & 0o077
    ):
        raise ResearchReviewError("MOJTRADE_PRIVATE_RESEARCH_DIRECTORY_UNSAFE")
    if not path.is_file():
        raise ResearchReviewError("MOJTRADE_PRIVATE_RESEARCH_MISSING")
    before = path.stat()
    if (
        not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
        or stat.S_IMODE(before.st_mode) & 0o077
        or before.st_size == 0 or before.st_size > MAX_SOURCE_BYTES
    ):
        raise ResearchReviewError("MOJTRADE_PRIVATE_RESEARCH_FILE_UNSAFE")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ResearchReviewError("MOJTRADE_REVIEW_CLOCK_NAIVE")
    current = current.astimezone(timezone.utc)
    original = _capped_read(path)
    try:
        result = read_observation(path, now=current)
    except ObservationError as exc:
        raise ResearchReviewError("MOJTRADE_PRIVATE_RESEARCH_CONTENT_REJECTED") from exc
    # The observer installs JSON through atomic replacement. Never combine
    # a report from one generation with a fingerprint from another.
    after = path.stat()
    second_read = _capped_read(path)
    identity = lambda item: (item.st_dev, item.st_ino, item.st_mtime_ns,
                             item.st_size, item.st_nlink)
    if identity(before) != identity(after) or original != second_read:
        raise ResearchReviewError("MOJTRADE_PRIVATE_RESEARCH_CHANGED_DURING_REVIEW")

    generated = datetime.fromisoformat(
        result["observation_generated_at"]
    ).astimezone(timezone.utc)
    expires = datetime.fromisoformat(
        result["observation_expires_at"]
    ).astimezone(timezone.utc)
    if expires - generated > MAX_OBSERVATION_WINDOW:
        raise ResearchReviewError("MOJTRADE_PRIVATE_RESEARCH_EXPIRY_TOO_LONG")
    sources = []
    for item in result["signals"]:
        observed = datetime.fromisoformat(item["observed_at"]).astimezone(timezone.utc)
        if observed > generated or current - observed > MAX_CANDLE_AGE:
            raise ResearchReviewError("MOJTRADE_PRIVATE_RESEARCH_CANDLE_STALE")
        sources.append({
            "symbol": item["symbol"],
            "stance": item["stance"],
            "data_source": item["data_source"],
            "observed_at": item["observed_at"],
            "signal_id": item["id"],
            "method": item["method"],
        })

    digest = hashlib.sha256(original).hexdigest()
    return {
        "schema": "mojtaba.bot.ai.private-market-research-review.v1",
        "canonical_agent": "economic-master-agent",
        "source_sha256": digest,
        "source_bytes": len(original),
        "observed_symbols": [item["symbol"] for item in sources],
        "observations": sources,
        "observation_generated_at": result["observation_generated_at"],
        "observation_expires_at": result["observation_expires_at"],
        "measurement": {
            "verified_observation_count": len(sources),
            "forward_outcome_samples": 0,
            "backtest_samples": 0,
            "win_rate": None,
            "verified_net_pnl": None,
            "independent_outcome_evidence": False,
        },
        "controls": {
            "research_only": True,
            "execution": "disabled",
            "orders": 0,
            "publication_enabled": False,
            "delivery_enabled": False,
            "financial_actions_enabled": False,
            "risk_per_live_trade": None,
            "live_strategy_approved": False,
        },
    }


def master_research_review(payload: dict) -> dict:
    """One existing master-agent gateway capability; no parallel agent."""
    if os.getenv("MOJ_FACTORY_LOCAL_MODE") != "1":
        raise ResearchReviewError("MOJTRADE_MASTER_PRIVATE_RUNTIME_ONLY")
    # task input is never permitted to choose a source file, symbol or order.
    if not isinstance(payload, dict):
        raise ResearchReviewError("MOJTRADE_MASTER_INPUT_INVALID")
    for forbidden in ("input_path", "source_path", "output_path", "order",
                      "trade", "broker", "wallet", "publish"):
        if forbidden in payload:
            raise ResearchReviewError("MOJTRADE_MASTER_UNAUTHORIZED_OVERRIDE")
    reviewed = inspect_private_observation(trusted_source())
    return {
        "action_performed": (
            "Validated two time-bounded private market research observations "
            "against the existing MojTrade source; no trade or publication."
        ),
        "verified_effect": True,
        "evidence": {
            "kind": "mojtrade_private_research_review",
            "value": reviewed,
        },
        "research_only": True,
        "performance_verified": False,
        "verified_revenue": None,
        "execution": "disabled",
        "orders": 0,
        "publication_enabled": False,
        "next_action": "await_independent_forward_market_outcomes",
    }
