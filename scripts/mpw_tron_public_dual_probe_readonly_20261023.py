"""Read-only, bounded TRON mainnet provider adapter.

The adapter is used only to obtain server-side evidence. It has no transfer,
wallet, signing, database, or customer-facing side effect.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import urllib.error
import urllib.request


NODES = (
    ("publicnode-allnodes", "https://tron-solidity-rpc.publicnode.com"),
    ("trongrid", "https://api.trongrid.io"),
)
_MAX_BYTES = 150_000


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise OSError("TRON RPC redirect rejected")


def _provider(provider):
    if (not isinstance(provider, (tuple, list)) or len(provider) != 2
            or tuple(provider) not in NODES):
        raise ValueError("Unapproved TRON provider")
    return tuple(provider)


def get(provider, kind, txid=None):
    source, base = _provider(provider)
    paths = {
        "head": "/walletsolidity/getnowblock",
        "body": "/walletsolidity/gettransactionbyid",
        "receipt": "/walletsolidity/gettransactioninfobyid",
    }
    if kind not in paths or (kind != "head" and
                              (not isinstance(txid, str) or len(txid) != 64)):
        raise ValueError("Invalid read-only TRON query")
    url = base + paths[kind]
    payload = {} if kind == "head" else {"value": txid, "visible": False}
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json",
                 "User-Agent": "MojPlayWin-TRON-Readonly/1.0"},
        method="POST",
    )
    try:
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=8) as response:
            if response.status != 200:
                raise OSError("Unexpected TRON RPC status")
            raw = response.read(_MAX_BYTES + 1)
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        raise OSError("TRON read-only provider unavailable") from exc
    if len(raw) > _MAX_BYTES:
        raise ValueError("TRON response too large")
    try:
        result = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("TRON response is not JSON") from exc
    if type(result) is not dict or result.get("Error"):
        raise ValueError("TRON provider returned an invalid result")
    return result


def head_height_and_age(block, now):
    if not isinstance(block, dict) or not isinstance(now, datetime):
        raise ValueError("Missing TRON head evidence")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Naive verification clock")
    raw = block.get("block_header", {}).get("raw_data", {})
    height, stamp = raw.get("number"), raw.get("timestamp")
    if type(height) is not int or height <= 0 or type(stamp) is not int or stamp <= 0:
        raise ValueError("Malformed TRON head")
    observed = datetime.fromtimestamp(stamp / 1000, timezone.utc)
    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    if not -10 <= age <= 180:
        raise ValueError("Stale TRON head")
    return height
