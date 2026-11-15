"""Offline, fail-closed native-TRON receiver readiness for independent domains.

This module DOES NOT activate a payment endpoint or contact a wallet/RPC.
It cannot prove wallet control or legal compliance from strings in a manifest;
it only rejects invalid/missing claims before manual external verification.
Do not store private keys, seed words, real consumer data or wallet signatures.
"""
import hashlib
import hmac
import re

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
REQUIRED_DOCUMENTATION = (
    "wallet_control_evidence_ref",
    "legal_review_evidence_ref",
    "independent_settlement_evidence_ref",
    "invoice_email_ownership_evidence_ref",
    "owner_separate_activation_approval_ref",
)


def tron_base58check_valid(address):
    """Require a TRON mainnet Base58Check account address, not just T-prefix."""
    if type(address) is not str or not 32 <= len(address) <= 36:
        return False
    if any(ch not in ALPHABET for ch in address):
        return False
    n = 0
    for char in address:
        n = n * 58 + ALPHABET.index(char)
    body = n.to_bytes((n.bit_length() + 7) // 8, "big")
    body = b"\x00" * (len(address) - len(address.lstrip("1"))) + body
    if len(body) != 25 or body[0] != 0x41:
        return False
    expected = hashlib.sha256(hashlib.sha256(body[:21]).digest()).digest()[:4]
    return hmac.compare_digest(body[21:], expected)


def domain_valid(domain):
    if type(domain) is not str or len(domain) > 253 or domain != domain.lower():
        return False
    if not re.fullmatch(r"[a-z0-9.-]+", domain) or ".." in domain:
        return False
    labels = domain.split(".")
    if len(labels) < 2:
        return False
    return all(1 <= len(label) <= 63 and label[0].isalnum()
               and label[-1].isalnum() for label in labels)


def assess_receiver_manifest(items):
    """Inventory public domain receiver declarations, never authorizing money.

    A populated evidence_ref is a *claim* needing independent owner review;
    no automatic evidence approval or live payment can result from this tool.
    Never echo receiving wallet addresses or evidence identifiers into reports.
    """
    if type(items) is not list:
        return {"gate": "blocked", "release_authorized": False,
                "errors": ["manifest_must_be_array"], "domains_checked": 0}
    errors, domains, wallets = [], set(), set()
    for index, entry in enumerate(items):
        if type(entry) is not dict:
            errors.append(f"row_{index}_invalid")
            continue
        domain = entry.get("domain")
        address = entry.get("receiver")
        if not domain_valid(domain):
            errors.append(f"row_{index}_invalid_domain")
        elif domain in domains:
            errors.append(f"row_{index}_duplicate_domain")
        else:
            domains.add(domain)
        if not tron_base58check_valid(address):
            errors.append(f"row_{index}_invalid_receiver_checksum_or_chain")
        elif address in wallets:
            errors.append(f"row_{index}_shared_wallet_not_independently_settled")
        else:
            wallets.add(address)
        for field in REQUIRED_DOCUMENTATION:
            value = entry.get(field)
            if type(value) is not str or not 1 <= len(value.strip()) <= 250:
                errors.append(f"row_{index}_missing_{field}")
        if entry.get("live_payments_enabled") is not False:
            errors.append(f"row_{index}_live_payment_must_remain_disabled")
    if not items:
        errors.append("no_domain_receivers")
    return {
        "gate": "blocked" if errors else "candidate_for_independent_owner_review",
        "release_authorized": False,
        "real_money_enabled": False,
        "domains_checked": len(domains),
        "errors": errors,
    }
