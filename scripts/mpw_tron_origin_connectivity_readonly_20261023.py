#!/usr/bin/env python3
"""Safe diagnostic: can this runtime read recent TRON solidified headers?

Never send transactions, mutate payments, read merchant keys or print RPC bodies.
Results include only public provider identifiers and connection health.
"""
from __future__ import annotations
import json
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone

SOURCES = (
    ("trongrid-mainnet", "https://api.trongrid.io/walletsolidity/getnowblock"),
    ("publicnode-mainnet", "https://tron-solidity-rpc.publicnode.com/walletsolidity/getnowblock"),
    ("trongrid-shasta-test", "https://api.shasta.trongrid.io/walletsolidity/getnowblock"),
)
MAX_BYTES = 5_000_000

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kw):
        return None

def read_one(label, url):
    result = {"provider": label, "read_only": True, "healthy_finalized_head": False}
    try:
        req = urllib.request.Request(url, method="GET", headers={
            "Accept": "application/json", "User-Agent": "MojPlayWin-Readonly-Diagnostic/1.0",
        })
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=12) as resp:
            result["http_status"] = resp.status
            if resp.status != 200 or resp.headers.get_content_type() != "application/json":
                raise ValueError("non_json_or_http_error")
            data = resp.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("oversized_finalized_head")
        head = json.loads(data)
        raw = head.get("block_header", {}).get("raw_data", {})
        block_no, millis = raw.get("number"), raw.get("timestamp")
        age = datetime.now(timezone.utc).timestamp() - millis / 1000 if type(millis) is int else 999999
        if type(block_no) is not int or block_no < 1 or not -60 <= age <= 600:
            raise ValueError("stale_or_invalid_finalized_header")
        result["healthy_finalized_head"] = True
        result["status"] = "READ_ONLY_OK"
    except urllib.error.HTTPError as exc:
        result["status"] = "HTTP_DENIED"
        result["http_status"] = exc.code
    except Exception as exc:
        result["status"] = "READ_ONLY_FAILED"
        result["error_class"] = type(exc).__name__
    return result

if __name__ == "__main__":
    print("MPW_TRON_ORIGIN_DIAGNOSTIC=" + json.dumps(
        {"financial_writes": 0, "checkout_activated": False,
         "providers": [read_one(*source) for source in SOURCES]},
        sort_keys=True,
    ))
