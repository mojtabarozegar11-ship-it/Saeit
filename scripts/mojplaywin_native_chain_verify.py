"""Pure TRON Base58Check address validation.

This module is deterministic and never broadcasts or contacts a network.
"""
from __future__ import annotations

import hashlib
import re


_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_ADDRESS = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")


class VerificationError(ValueError):
    """The address is not a valid canonical TRON mainnet address."""


def _decode_base58(value: str) -> bytes:
    number = 0
    for char in value:
        try:
            digit = _ALPHABET.index(char)
        except ValueError as exc:
            raise VerificationError("Invalid Base58 character") from exc
        number = number * 58 + digit
    raw = number.to_bytes(max(1, (number.bit_length() + 7) // 8), "big")
    leading = len(value) - len(value.lstrip("1"))
    return b"\x00" * leading + raw.lstrip(b"\x00")


def tron_address_to_hex(address: str) -> str:
    """Return the 21-byte 0x41-prefixed payload as lowercase hexadecimal."""
    if type(address) is not str or _ADDRESS.fullmatch(address) is None:
        raise VerificationError("Malformed TRON mainnet address")
    decoded = _decode_base58(address)
    if len(decoded) != 25:
        raise VerificationError("Unexpected TRON address length")
    payload, checksum = decoded[:21], decoded[21:]
    expected = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    if checksum != expected or payload[:1] != b"\x41":
        raise VerificationError("TRON Base58Check checksum/network mismatch")
    return payload.hex()
