"""Server-issued, invoice-bound TRON wallet proof contract for Starter30.

SOURCE-ONLY and not connected to production. It never verifies a signature
without a supplied, audited TronWeb v2 recovery implementation or consumes a
nonce without a supplied durable atomic claim callback. Neither failure may
ever silently become a successful buyer identity.

TronLink signs the *literal plaintext message* with signMessageV2(message).
A trusted server-side Trx.verifyMessageV2 implementation recovers a base58
signer and MUST compare it to the invoice-bound sender. Email verification
and knowing another person's public TRON address are not wallet possession.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from typing import Callable

from django.core import signing
from services.mpw_trx_merchant_binding import validate_tron_recipient

_TAG = "mojprop-starter30-wallet-control-v1"
_DOMAIN = "mojplaywin.com"
_NETWORK = "tron-mainnet"
_AMOUNT_SUN = 30_000_000
_MAX_AGE_SECONDS = 600
_TRON = re.compile(r"T[1-9A-HJ-NP-Za-km-z]{33}\Z")
_DIGEST = re.compile(r"[a-f0-9]{64}\Z")
_REFERENCE = re.compile(r"[A-Za-z0-9_-]{8,100}\Z")
_SIGNATURE = re.compile(r"0x[a-fA-F0-9]{130}\Z")


class WalletProofUnavailable(ValueError):
    """Never silently accept an unauthenticated or ambiguous wallet."""


def _validated_public_address(value: str) -> str:
    # Enforce actual Base58Check checksum locally, not just a leading T.
    # A chain prefix alone cannot distinguish mainnet from test networks;
    # the separate server-signed challenge fixes the intended network.
    if type(value) is not str or _TRON.fullmatch(value) is None:
        raise WalletProofUnavailable("invalid TRON wallet address")
    try:
        return validate_tron_recipient(value)
    except ValueError as exc:
        raise WalletProofUnavailable("invalid TRON wallet checksum") from exc


def _message(payload: dict) -> str:
    """Canonical plaintext: no JSON stringify/locale/timezone ambiguities."""
    return "\n".join((
        "MojPlayWin Starter30 wallet ownership",
        "Origin: https://mojplaywin.com",
        "Network: tron-mainnet",
        "Purpose: Prove sending wallet control, not a transfer",
        f"Buyer identity SHA256: {payload['buyer']}",
        f"Invoice: {payload['invoice']}",
        f"Sending wallet: {payload['sender']}",
        f"Receiving wallet: {payload['recipient']}",
        "Amount: 30000000 SUN (30 TRX)",
        f"Terms SHA256: {payload['terms']}",
        f"Nonce: {payload['nonce']}",
        "This signature does not send TRX or grant an account.",
    ))


def issue_wallet_proof_challenge(
    *, invoice_ref: str, buyer_digest: str, sender: str,
    recipient: str, terms_digest: str,
) -> tuple[str, str]:
    """Return signed server ticket and exact wallet-signable message.

    This DOES NOT allocate an invoice or mark a payment paid. Caller must
    already have validated buyer email, one owner-approved recipient and
    an immutable invoice before calling this function.
    """
    if type(invoice_ref) is not str or not _REFERENCE.fullmatch(invoice_ref):
        raise WalletProofUnavailable("invalid invoice reference")
    if type(buyer_digest) is not str or not _DIGEST.fullmatch(buyer_digest):
        raise WalletProofUnavailable("invalid buyer digest")
    if type(terms_digest) is not str or not _DIGEST.fullmatch(terms_digest):
        raise WalletProofUnavailable("invalid contract digest")
    sender = _validated_public_address(sender)
    recipient = _validated_public_address(recipient)
    if hmac.compare_digest(sender, recipient):
        raise WalletProofUnavailable("sending wallet cannot receive this invoice")
    payload = {
        "v": 1,
        "host": _DOMAIN,
        "chain": _NETWORK,
        "amount": _AMOUNT_SUN,
        "invoice": invoice_ref,
        "buyer": buyer_digest,
        "sender": sender,
        "recipient": recipient,
        "terms": terms_digest,
        "nonce": secrets.token_hex(32),
    }
    ticket = signing.dumps(payload, salt=_TAG, compress=False)
    return ticket, _message(payload)


def verify_wallet_proof(
    *, ticket: str, message: str, signature: str,
    expected_invoice: str, expected_buyer_digest: str,
    expected_sender: str, expected_recipient: str,
    expected_terms_digest: str,
    recover_signer: Callable[[str, str], str] | None,
    claim_nonce_once: Callable[[str, str], bool] | None,
) -> str:
    """Fail closed and return verified TRON address ONLY after atomic claim.

    recover_signer MUST be an audited server-side TronWeb v2 recovery adapter,
    not a browser-provided `verified` boolean or an inferred transfer sender.
    claim_nonce_once MUST atomically reject the same (nonce_digest, invoice)
    after first use, using shared durable storage and appropriate expiration.
    If either implementation is absent, no verification is possible.
    """
    if recover_signer is None or claim_nonce_once is None:
        raise WalletProofUnavailable("server-side signature or replay protection unavailable")
    if not callable(recover_signer) or not callable(claim_nonce_once):
        raise WalletProofUnavailable("untrusted verification adapter")
    if type(ticket) is not str or not ticket or len(ticket) > 4096:
        raise WalletProofUnavailable("invalid challenge ticket")
    if type(message) is not str or not message or len(message) > 1800:
        raise WalletProofUnavailable("invalid signed message")
    if type(signature) is not str or _SIGNATURE.fullmatch(signature) is None:
        raise WalletProofUnavailable("invalid signature encoding")
    try:
        payload = signing.loads(ticket, salt=_TAG, max_age=_MAX_AGE_SECONDS)
    except signing.BadSignature as exc:
        raise WalletProofUnavailable("invalid or expired challenge") from exc
    if type(payload) is not dict or payload.get("v") != 1:
        raise WalletProofUnavailable("invalid challenge format")
    if payload.get("host") != _DOMAIN or payload.get("chain") != _NETWORK:
        raise WalletProofUnavailable("challenge is for another site or network")
    if type(payload.get("amount")) is not int or payload["amount"] != _AMOUNT_SUN:
        raise WalletProofUnavailable("challenge price mismatch")
    for field, expected in (
        ("invoice", expected_invoice), ("buyer", expected_buyer_digest),
        ("sender", expected_sender), ("recipient", expected_recipient),
        ("terms", expected_terms_digest),
    ):
        observed = payload.get(field)
        if type(observed) is not str or type(expected) is not str or not hmac.compare_digest(observed, expected):
            raise WalletProofUnavailable("challenge does not match this invoice")
    nonce = payload.get("nonce")
    if type(nonce) is not str or not re.fullmatch(r"[a-f0-9]{64}", nonce):
        raise WalletProofUnavailable("invalid challenge nonce")
    # A signed message may never be substituted with a different invoice,
    # recipient, price, contract or random consent text.
    if not hmac.compare_digest(message, _message(payload)):
        raise WalletProofUnavailable("signed message differs from the server challenge")
    try:
        recovered = recover_signer(message, signature)
    except Exception as exc:
        raise WalletProofUnavailable("cryptographic signer recovery failed") from exc
    if type(recovered) is not str or not hmac.compare_digest(recovered, expected_sender):
        raise WalletProofUnavailable("wallet signature does not match invoice sender")
    nonce_hash = hashlib.sha256((_TAG + ":" + nonce).encode("ascii")).hexdigest()
    try:
        consumed = claim_nonce_once(nonce_hash, expected_invoice)
    except Exception as exc:
        raise WalletProofUnavailable("durable nonce ledger unavailable") from exc
    if consumed is not True:
        raise WalletProofUnavailable("challenge already used or replay guard failed")
    return recovered
