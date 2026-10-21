"""Two-operator finalized TRX confirmation. Source-only, opt-in, read-only.

Each source must be provisioned by a trusted operator and independently backed
by a distinct SolidityNode provider; names alone do NOT prove independence.
Never obtain provider URLs, identities or credentials from browser/webhook data.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from django.conf import settings

from .services import CommerceRejected, CommerceUnavailable
from .tron_verifier import independently_verify_finalized_trx


@dataclass(frozen=True)
class TrustedSoliditySource:
    # Opaque name for operator inventory (not a URL or customer-visible value).
    operator_id: str
    # Trusted backend function: (txid: str, *, api_key: str) -> (body, receipt)
    fetch: Callable
    api_key: str = ''


def verify_two_source_finalized_trx(event, purchase, *, sources=None):
    """Require two independent trusted finalized body+receipt confirmations.

    The function intentionally does NOT include a live secondary RPC URL or
    mutate payment/order records. Any unavailable, divergent or unconfigured
    source leaves the buyer WITHOUT an entitlement and prompts retry/review.
    Set MOJ_COMMERCE_FINALIZED_TRON_CHECKER to this callable ONLY after
    real independent provider identity and finality checks are approved.
    """
    if sources is None:
        sources = getattr(settings, 'MOJ_COMMERCE_TRON_QUORUM_SOURCES', None)
    if not isinstance(sources, (tuple, list)) or len(sources) != 2:
        raise CommerceUnavailable('Two trusted finalized TRON read sources required')
    one, two = sources
    if (not isinstance(one, TrustedSoliditySource) or
        not isinstance(two, TrustedSoliditySource)):
        raise CommerceUnavailable('Invalid trusted finalized source configuration')
    for source in (one, two):
        if (not isinstance(source.operator_id, str) or
            not re.fullmatch(r'[a-z][a-z0-9_-]{2,39}', source.operator_id) or
            not callable(source.fetch) or
            not isinstance(source.api_key, str) or
            len(source.api_key) > 512 or
            '\n' in source.api_key or '\r' in source.api_key):
            raise CommerceUnavailable('Invalid trusted finalized source configuration')
    if one.operator_id == two.operator_id or one.fetch is two.fetch:
        raise CommerceUnavailable('Sources must be distinct independently operated readers')

    proof_a = proof_b = None
    try:
        proof_a = independently_verify_finalized_trx(
            event, purchase, fetch=one.fetch, api_key=one.api_key)
        proof_b = independently_verify_finalized_trx(
            event, purchase, fetch=two.fetch, api_key=two.api_key)
    except (CommerceRejected, CommerceUnavailable) as exc:
        # No one-source fallback: even a malformed/failed second receipt is
        # never enough proof to deliver. Source details stay private.
        raise CommerceUnavailable('Finalized TRON quorum not established') from exc
    if proof_a != proof_b or not proof_a.get('confirmed') or not proof_b.get('confirmed'):
        raise CommerceUnavailable('Finalized TRON sources disagree')
    return proof_a
