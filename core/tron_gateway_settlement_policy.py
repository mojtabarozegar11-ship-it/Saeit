"""Pure canonical TRON mainnet proof policy for an irreversible DB claim.

This is *only* structural validation. The caller MUST independently verify
native TRX finality/amount/receiver through the pinned solidified RPC nodes.
"""
from __future__ import annotations
import re

_TXID = re.compile(r"[0-9a-f]{64}\\Z")
_SENDER = re.compile(r"41[0-9a-f]{40}\\Z")


class InvalidSettlementProof(ValueError):
    """Missing, malformed, or unfinalized proof; do not write payment records."""


def canonical_settlement_claim(proof):
    """Return immutable canonical claim fields; fail closed on any ambiguity."""
    if type(proof) is not dict:
        raise InvalidSettlementProof("Invalid finalized proof object")
    txid = proof.get("txid")
    digest = proof.get("proof_digest")
    sender = proof.get("sender_hex")
    height = proof.get("block_height")
    timestamp = proof.get("block_time_ms")
    if (type(txid) is not str or _TXID.fullmatch(txid.lower()) is None
            or type(digest) is not str or _TXID.fullmatch(digest) is None
            or type(sender) is not str or _SENDER.fullmatch(sender) is None
            or type(height) is not int or height <= 0
            or type(timestamp) is not int or timestamp <= 0
            or proof.get("finality") != "solidified"):
        raise InvalidSettlementProof("Noncanonical or nonfinalized TRON payment proof")
    return {"txid": txid.lower(), "proof_digest": digest}
