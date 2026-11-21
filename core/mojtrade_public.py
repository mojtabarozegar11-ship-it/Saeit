"""Read-only, fail-closed public snapshot for the independent MojTrade VPS.

The site never obtains broker keys, signs orders or executes trades. A separate
publisher may install an HMAC-signed snapshot outside the public document root.
No snapshot is published until the operator explicitly enables publication.
"""

import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


MARKETS = ("crypto", "forex", "equities", "commodities", "indices", "bonds", "funds")
MAX_FILE_BYTES = 96_000
MAX_SIGNALS = 25
MAX_AGE = timedelta(hours=24)
ALLOWED_ORIGINS = frozenset({
    "https://zomorodmelal.ir", "https://www.zomorodmelal.ir",
    "https://mojplaywin.com", "https://www.mojplaywin.com",
})


def _parse_time(value):
    if not isinstance(value, str):
        raise ValueError("invalid timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must specify timezone")
    return parsed.astimezone(timezone.utc)


def _validate_payload(payload, now):
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version", "generated_at", "expires_at", "source", "signals",
    }:
        raise ValueError("invalid schema")
    if payload["schema_version"] != 1 or payload["source"] != "mojtrade-vps":
        raise ValueError("unsupported producer")
    generated = _parse_time(payload["generated_at"])
    expires = _parse_time(payload["expires_at"])
    if generated > now + timedelta(minutes=2) or expires <= generated or expires - generated > MAX_AGE:
        raise ValueError("invalid validity interval")
    if now > expires:
        raise ValueError("expired snapshot")
    items = payload["signals"]
    if not isinstance(items, list) or len(items) > MAX_SIGNALS:
        raise ValueError("invalid signal count")
    seen = set()
    validated = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {
            "id", "market", "symbol", "timeframe", "stance", "observed_at",
            "method", "data_source",
        }:
            raise ValueError("invalid signal fields")
        if item["market"] not in MARKETS or item["stance"] not in {"watch_buy", "watch_sell", "neutral"}:
            raise ValueError("invalid market or stance")
        if not all(isinstance(item[k], str) and 1 <= len(item[k]) <= 120 for k in (
            "id", "symbol", "timeframe", "method", "data_source"
        )):
            raise ValueError("invalid string fields")
        if item["id"] in seen:
            raise ValueError("duplicate signal")
        seen.add(item["id"])
        observed = _parse_time(item["observed_at"])
        if observed > generated or observed < generated - MAX_AGE:
            raise ValueError("invalid signal time")
        validated.append(item)
    return validated


def _load_verified_snapshot(now):
    filename = os.environ.get("MOJTRADE_PUBLIC_FEED_PATH", "")
    secret = os.environ.get("MOJTRADE_PUBLIC_FEED_HMAC_KEY", "")
    if not filename or len(secret) < 32:
        return None, "not_configured"
    target = Path(filename)
    if not target.is_absolute() or target.is_symlink() or not target.is_file():
        return None, "missing_or_unsafe_feed"
    if target.stat().st_size > MAX_FILE_BYTES:
        return None, "oversized_feed"
    try:
        envelope = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(envelope, dict) or set(envelope) != {"payload", "signature"}:
            raise ValueError("invalid envelope")
        payload = envelope["payload"]
        signature = envelope["signature"]
        if not isinstance(signature, str) or len(signature) != 64:
            raise ValueError("invalid signature")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        expected = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature mismatch")
        signals = _validate_payload(payload, now)
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, OverflowError):
        return None, "unverified_or_expired_feed"
    return (payload, signals), "verified"


@never_cache
@require_GET
def public_snapshot(request):
    """Same canonical read-only feed for Zahra, MojPlayWin and Zomorod Melal."""
    now = datetime.now(timezone.utc)
    verified, status = _load_verified_snapshot(now)
    publication_enabled = os.environ.get("MOJTRADE_PUBLICATION_ENABLED", "").lower() == "true"
    result = {
        "schema_version": 1,
        "service": "MojTrade AI",
        "status": status if verified else "offline",
        "reason": "" if verified else status,
        "execution_mode": "disabled",
        "live_trading_enabled": False,
        "markets": list(MARKETS),
        "generated_at": verified[0]["generated_at"] if verified else None,
        "signals": verified[1] if verified and publication_enabled else [],
        "signal_publication": "enabled" if verified and publication_enabled else "disabled",
    }
    if verified and not publication_enabled:
        result["status"] = "verified_private"
    response = JsonResponse(result, json_dumps_params={"ensure_ascii": False})
    response["Cache-Control"] = "no-store, max-age=0"
    response["X-Content-Type-Options"] = "nosniff"
    origin = request.headers.get("Origin", "")
    if origin in ALLOWED_ORIGINS:
        response["Access-Control-Allow-Origin"] = origin
        response["Vary"] = "Origin"
    return response
