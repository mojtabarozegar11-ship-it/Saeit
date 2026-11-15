"""Single-agent educational market-brief publication policy.

This module validates source-backed educational analysis for mojtaba.bot.ai.
It does not generate a market price, transmit a signal, manage subscriptions,
send messages, trade, or collect payments. The source evidence and review must
come from an independently accountable workflow.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
import ipaddress
from urllib.parse import urlsplit


class SignalRecordError(ValueError):
    pass


ASSET = re.compile(r"[A-Z0-9][A-Z0-9:/._-]{2,31}\Z")
REVIEWER = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{2,63}\Z")
ALLOWED_TIMEFRAMES = frozenset(("1m", "5m", "15m", "1h", "4h", "1d", "1w"))
RISK_DISCLAIMER = (
    "Educational scenario, not personalized financial advice; "
    "market conditions may change and loss of capital is possible."
)


@dataclass(frozen=True)
class EducationalSignal:
    record_id: str
    asset: str
    timeframe: str
    scenario: str
    invalidation: str
    evidence_url: str
    observed_at: datetime
    reviewed_at: datetime
    reviewer_id: str
    risk_statement: str
    as_of: datetime
    author_agent: str = "mojtaba.bot.ai"


def _meaningful(value, name, *, minimum=15, maximum=1500):
    if (type(value) is not str or not minimum <= len(value.strip()) <= maximum
            or any((ord(ch) < 32 and ch not in "\n\t")
                   or 0xD800 <= ord(ch) <= 0xDFFF for ch in value)):
        raise SignalRecordError("invalid " + name)
    return value.strip()


def _aware(value, name):
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise SignalRecordError("timezone-aware " + name + " required")
    return value.astimezone(timezone.utc)


def review_signal(record: EducationalSignal, *, now: datetime | None = None):
    """Validate source, authorship, review, timeliness and loss disclosure.

    Return a stable source-content fingerprint for provenance; not a sale, a
    live market feed, an automatic trade or a guarantee of performance.
    """
    if type(record) is not EducationalSignal or record.author_agent != "mojtaba.bot.ai":
        raise SignalRecordError("single authorized agent identity required")
    if type(record.record_id) is not str or not REVIEWER.fullmatch(record.record_id):
        raise SignalRecordError("invalid record id")
    if type(record.asset) is not str or not ASSET.fullmatch(record.asset):
        raise SignalRecordError("invalid asset")
    if type(record.timeframe) is not str or record.timeframe not in ALLOWED_TIMEFRAMES:
        raise SignalRecordError("invalid timeframe")
    if type(record.reviewer_id) is not str or not REVIEWER.fullmatch(record.reviewer_id):
        raise SignalRecordError("reviewer identity required")
    scenario = _meaningful(record.scenario, "educational scenario", minimum=40)
    invalidation = _meaningful(record.invalidation, "invalidation", minimum=35)
    disclosure = _meaningful(record.risk_statement, "risk disclosure", minimum=40)
    if "loss" not in disclosure.casefold() or "educational" not in disclosure.casefold():
        raise SignalRecordError("loss-risk and educational disclosures required")
    if (any(word in scenario.casefold() for word in (
            "guaranteed profit", "risk free", "guaranteed return"
    ))):
        raise SignalRecordError("prohibited guaranteed-performance claim")
    # URL splitting normalizes embedded tabs/newlines and may raise on invalid
    # IPv6 or ports. Fail closed rather than allowing an unhandled 500 response.
    if (type(record.evidence_url) is not str
            or not 1 <= len(record.evidence_url) <= 500
            or any(ord(ch) <= 32 or 0x7F <= ord(ch) <= 0x9F
                   or 0xD800 <= ord(ch) <= 0xDFFF
                   for ch in record.evidence_url)
            or "\\" in record.evidence_url):
        raise SignalRecordError("independent HTTPS source URL required")
    try:
        url = urlsplit(record.evidence_url)
        host = url.hostname
        port = url.port  # evaluate: invalid explicit port must be rejected
    except ValueError as exc:
        raise SignalRecordError("malformed HTTPS source URL") from exc
    if (url.scheme != "https" or not host or url.username is not None
            or url.password is not None or not host.count(".") or url.fragment
            or port == 0):
        raise SignalRecordError("independent HTTPS source URL required")
    # Prevent private-network and self-owned evidence domains from being
    # treated as independent sources by a future server-side fetch adapter.
    if (not host.isascii() or host.endswith(".")
            or host.endswith((".localhost", ".local", ".internal"))
            or host.lower() in ("localhost", "mojtaba.bot.ai", "mojplaywin.com", "zomorodmelal.ir")
            or host.lower().endswith((".mojtaba.bot.ai", ".mojplaywin.com", ".zomorodmelal.ir"))):
        raise SignalRecordError("self-owned or private evidence host forbidden")
    try:
        literal_host = ipaddress.ip_address(host)
    except ValueError:
        literal_host = None
    if literal_host is not None and not literal_host.is_global:
        raise SignalRecordError("private IP evidence source forbidden")
    # URL validation is still not DNS pinning or a live source attestation.
    observed = _aware(record.observed_at, "observed_at")
    reviewed = _aware(record.reviewed_at, "reviewed_at")
    as_of = _aware(record.as_of, "as_of")
    moment = _aware(now or datetime.now(timezone.utc), "now")
    if not (moment - timedelta(hours=24) <= observed <= reviewed <= as_of <= moment
            and as_of - observed <= timedelta(hours=24)):
        raise SignalRecordError("stale, future or incorrectly ordered source evidence")
    body = {
        "record_id": record.record_id, "asset": record.asset,
        "timeframe": record.timeframe, "scenario": scenario,
        "invalidation": invalidation,
        "evidence_url": record.evidence_url,
        "observed_at": observed.isoformat(),
        "reviewed_at": reviewed.isoformat(),
        "as_of": as_of.isoformat(), "reviewer_id": record.reviewer_id,
        "risk_statement": disclosure, "author_agent": record.author_agent,
    }
    fingerprint = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    # Syntactically valid HTTPS URLs are not proof of independently
    # observed live market data. Never mark content publishable or billed
    # until a separate audited source adapter and commercial contract pass.
    return {"record": body, "evidence_fingerprint": fingerprint,
            "content_policy_passed": True,
            "independent_source_verified": False,
            "publication_allowed": False,
            "delivery_confirmed": False, "payment_received": False}


def manual_signal_offer_for_plan(plan_id):
    """Expose the fixed catalog through the single-agent policy boundary."""
    from .mojtaba_signal_catalog import build_manual_signal_offer
    result = build_manual_signal_offer(plan_id)
    result["content_policy_passed"] = True
    result["publication_allowed"] = False
    result["payment_received"] = False
    return result
