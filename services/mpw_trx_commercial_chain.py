"""Bounded independent mainnet TRX evidence for an owner-issued invoice.

Never infer settlement from merchant indexer data or browser callbacks.
This adapter only constructs verified finalized evidence for an existing
transaction; accounting is exclusively in the merchant database adapter.
"""
from __future__ import annotations
from datetime import datetime,timezone
import json
import re
import urllib.request
from services.mpw_trx_walletless_core import PaymentHold, TX_ID
from services.mpw_tron_independent_solidified_rpc import parse_solidified_native_trx
from services.mpw_walletless_django_test_bridge import TrustedNodePair
from scripts.mpw_tron_public_dual_probe_readonly_20261023 import (
    NODES, get, head_height_and_age,
)

PINNED=(("publicnode-allnodes","https://tron-solidity-rpc.publicnode.com"),
        ("trongrid","https://api.trongrid.io"))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _bounded_solidified_head(provider):
    """Parse a complete JSON block_header without downloading huge chunked blocks.

    PublicNode Solidity head replies can stream transaction lists indefinitely.
    Only this limited head read is optimized; transaction bodies and receipts
    still require complete independently verified JSON from each pinned operator.
    """
    if provider not in PINNED:
        raise ValueError("Unapproved solidity head operator")
    req = urllib.request.Request(
        provider[1] + "/walletsolidity/getnowblock",
        headers={"Accept": "application/json",
                 "User-Agent": "MojPlayWin-Readonly-Diagnostic/1.0"},
        method="GET",
    )
    with urllib.request.build_opener(_NoRedirect()).open(req, timeout=12) as response:
        if response.status != 200 or response.headers.get_content_type() != "application/json":
            raise ValueError("Invalid finalized head HTTP response")
        buffer = b""
        for _ in range(8):
            chunk = response.read(4096)
            if not chunk:
                break
            buffer += chunk
            match = re.search(rb'"block_header"\s*:\s*{', buffer)
            if match is None:
                continue
            start = match.end() - 1
            depth = 0
            in_string = False
            escaped = False
            for end in range(start, len(buffer)):
                byte = buffer[end]
                if in_string:
                    if escaped:
                        escaped = False
                    elif byte == 92:
                        escaped = True
                    elif byte == 34:
                        in_string = False
                elif byte == 34:
                    in_string = True
                elif byte == 123:
                    depth += 1
                elif byte == 125:
                    depth -= 1
                    if depth == 0:
                        header = json.loads(buffer[start:end + 1])
                        if type(header) is not dict:
                            raise ValueError("Invalid finalized header payload")
                        return {"block_header": header}
    raise ValueError("Bounded finalized header not available")


def read_only_independent_pair():
    """Require both network heads fresh; no transaction broadcasting."""
    if tuple(NODES)!=PINNED:
        raise PaymentHold("Unexpected mainnet verifier providers")
    now=datetime.now(timezone.utc)
    try:
        heights=[head_height_and_age(_bounded_solidified_head(provider),now) for provider in PINNED]
    except (OSError,ValueError,TypeError,KeyError) as exc:
        raise PaymentHold("Mainnet solidified head proof unavailable") from exc
    if abs(heights[0]-heights[1])>100:
        raise PaymentHold("Independent finalized nodes disagree on head range")
    def read(index,tx):
        if not isinstance(tx,str) or TX_ID.fullmatch(tx) is None:
            raise PaymentHold("Untrusted transaction candidate")
        provider=PINNED[index]
        try:
            body=get(provider,"body",tx)
            receipt=get(provider,"receipt",tx)
            return parse_solidified_native_trx(tx,body,receipt,source_id=provider[0])
        except (OSError,ValueError,TypeError,KeyError) as exc:
            raise PaymentHold("Independent solidity transfer not available") from exc
    return TrustedNodePair(
        identifier_a=PINNED[0][0],
        identifier_b=PINNED[1][0],
        prove_a=lambda tx:read(0,tx),
        prove_b=lambda tx:read(1,tx),
        audited_as_independent=True,
    )
