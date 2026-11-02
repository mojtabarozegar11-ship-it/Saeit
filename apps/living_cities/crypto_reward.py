"""MOJ1 reward asset policy for Living Cities.

This module never signs transactions or credits a spendable cryptocurrency balance.
Owner-selected currency/network alone are insufficient to approve a blockchain payout.
"""
import hashlib
import os

TOKEN_SYMBOL = "MOJ1"
TOKEN_NETWORK = "TRON"
TOKEN_STANDARD = "TRC-20"
B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def valid_tron_address(value):
    """TRON Base58Check validation, including 0x41 network prefix and checksum."""
    if type(value) is not str or len(value) != 34 or any(c not in B58_ALPHABET for c in value):
        return False
    number = 0
    for character in value:
        number = number * 58 + B58_ALPHABET.index(character)
    raw = number.to_bytes(25, "big")
    checksum = hashlib.sha256(hashlib.sha256(raw[:21]).digest()).digest()[:4]
    return raw[0] == 0x41 and raw[21:] == checksum


def reward_policy():
    contract = os.environ.get("LIVING_CITIES_MOJ1_CONTRACT_ADDRESS", "").strip()
    plausible = valid_tron_address(contract)
    # A syntactically valid address does not prove token identity, deployer control,
    # independent audit, available balances or permission to distribute.
    return {
        "symbol": TOKEN_SYMBOL,
        "network": TOKEN_NETWORK,
        "standard": TOKEN_STANDARD,
        "contract_address_configured": plausible,
        "contract_identity_verified": False,
        "independent_audit_verified": False,
        "recipient_payout_enabled": False,
        "payout_reason": "requires_verified_contract_audit_funding_and_regulatory_clearance",
    }
