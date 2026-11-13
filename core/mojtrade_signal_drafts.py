"""Private multilingual market-watch drafts from validated canonical MojTrade evidence.

These are time-limited research alerts, NOT entry/exit trade instructions,
public signals, investment advice, broker quotes or evidence of profit.
No network, email, publication, payments or broker access is possible here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json

from .mojtrade_strategy_risk import MODEL_VERSION


SCHEMA = "mojtaba.bot.ai.mojtrade-market-watch-draft.v1"

# Fixed reviewed copy: never interpolate untrusted source text into prose.
COPY = {
    "fa": {
        "monitor_bullish": "رصد روند صعودی؛ سیگنال ورود صادر نشده است.",
        "monitor_bearish": "رصد روند نزولی؛ سیگنال ورود صادر نشده است.",
        "no_setup": "موقعیت معتبر شناسایی نشده؛ بدون اقدام معاملاتی.",
    },
    "en": {
        "monitor_bullish": "Bullish trend watch; no entry signal issued.",
        "monitor_bearish": "Bearish trend watch; no entry signal issued.",
        "no_setup": "No validated setup; no trading action.",
    },
    "ar": {
        "monitor_bullish": "مراقبة اتجاه صاعد؛ لم تصدر إشارة دخول.",
        "monitor_bearish": "مراقبة اتجاه هابط؛ لم تصدر إشارة دخول.",
        "no_setup": "لا توجد فرصة مؤكدة؛ لا إجراء تداول.",
    },
}
SYMBOLS = ("BTC/USD", "ETH/USD")
CLASSIFICATIONS = frozenset(("monitor_bullish", "monitor_bearish", "no_setup"))


class MarketWatchDraftError(ValueError):
    """Refuse stale, mismatched or externally executable signal drafts."""


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise MarketWatchDraftError(label + "_missing")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise MarketWatchDraftError(label + "_invalid") from exc
    if dt.tzinfo is None:
        raise MarketWatchDraftError(label + "_timezone_required")
    return dt.astimezone(timezone.utc)


def build_market_watch_drafts(
    report: dict, review: dict, source_sha256: str, *, now: datetime | None = None,
) -> dict:
    """Materialize fixed-copy, 3-language private alerts from one verified receipt.

    Signal IDs and classification are bound to the original reviewed decision,
    not recalculated or invented. Expiry is mandatory; no public distribution.
    """
    if not isinstance(report, dict) or not isinstance(review, dict):
        raise MarketWatchDraftError("validated_review_required")
    if (report.get("execution") != "disabled" or report.get("orders") != 0
            or report.get("action") != "research_only"
            or review.get("schema") != MODEL_VERSION
            or review.get("execution") != "disabled"
            or review.get("orders") != 0
            or review.get("broker_connected") is not False
            or review.get("executable_order_intents") != []):
        raise MarketWatchDraftError("nonexecutable_review_required")
    if not isinstance(source_sha256, str) or len(source_sha256) != 64 or any(
        c not in "0123456789abcdef" for c in source_sha256
    ):
        raise MarketWatchDraftError("source_digest_invalid")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise MarketWatchDraftError("now_timezone_required")
    current = current.astimezone(timezone.utc)
    generated = _utc(report.get("observation_generated_at"), "generated")
    expires = _utc(report.get("observation_expires_at"), "expires")
    if not generated <= current < expires or (expires - generated).total_seconds() > 5400:
        raise MarketWatchDraftError("observation_expired_or_invalid")
    signals, decisions = report.get("signals"), review.get("decisions")
    if (not isinstance(signals, list) or not isinstance(decisions, list)
            or len(signals) != 2 or len(decisions) != 2):
        raise MarketWatchDraftError("source_review_cardinality_mismatch")
    digest = hashlib.sha256(json.dumps(
        {"version": MODEL_VERSION, "decisions": decisions},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")).hexdigest()
    if review.get("decision_digest_sha256") != digest:
        raise MarketWatchDraftError("review_digest_mismatch")
    items = []
    for index, (source, decision) in enumerate(zip(signals, decisions)):
        if not isinstance(source, dict) or not isinstance(decision, dict):
            raise MarketWatchDraftError("source_review_invalid")
        classification = decision.get("classification")
        if (source.get("symbol") != SYMBOLS[index]
                or decision.get("symbol") != SYMBOLS[index]
                or decision.get("source_signal_id") != source.get("id")
                or decision.get("source_provider") != source.get("data_source")
                or decision.get("source_observed_at") != source.get("observed_at")
                or decision.get("source_method") != source.get("method")
                or classification not in CLASSIFICATIONS
                or decision.get("risk_gate") != "blocked_missing_broker_verified_inputs"
                or decision.get("execution_authorized") is not False
                or decision.get("order_intent") is not None):
            raise MarketWatchDraftError("review_does_not_match_validated_source")
        observed = _utc(source.get("observed_at"), "observed")
        if observed > generated or generated - observed > timedelta(hours=3):
            raise MarketWatchDraftError("source_candle_too_old")
        items.append({
            "symbol": SYMBOLS[index],
            "source_signal_id": source["id"],
            "observed_at": observed.isoformat(),
            "source_provider": source["data_source"],
            "method": source["method"],
            "classification": classification,
            "content": {lang: texts[classification] for lang, texts in COPY.items()},
            "entry_price": None, "stop_loss": None, "take_profit": None,
            "order_intent": None, "execution_authorized": False,
        })
    payload = {
        "schema": SCHEMA,
        "canonical_owner": "mojtaba-bot-ai",
        "source_sha256": source_sha256,
        "decision_sha256": review.get("decision_digest_sha256"),
        "observation_generated_at": generated.isoformat(),
        "expires_at": expires.isoformat(),
        "status": "private_owner_review_only",
        "languages": list(COPY),
        "alerts": items,
        "publication_authorized": False,
        "external_delivery_receipts": [],
        "broker_connected": False,
        "trade_execution_authorized": False,
        "executed_orders": 0,
        "revenue_verified": False,
        "profit_verified": False,
    }
    # Content-addressed identity supports deduplication by a later authorized
    # distributor without exposing private raw market data or issuing an order.
    packed = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    payload["draft_sha256"] = hashlib.sha256(packed.encode("utf-8")).hexdigest()
    return payload
