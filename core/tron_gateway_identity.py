"""Control-character-safe buyer email normalization for the native-TRX checkout.

The Django email validator is supplied by the caller; this pure policy also
runs offline. A successful normalization never establishes email ownership.
"""
from __future__ import annotations

import unicodedata


def normalize_buyer_email(raw: str, validator) -> str:
    """Canonicalize an email without silently erasing unsafe input characters.

    Printable surrounding spaces are tolerated; raw control, format and
    surrogate characters are *not* stripped, transformed or emailed.
    The caller's validator remains responsible for syntactic/domain validity.
    """
    if type(raw) is not str:
        raise ValueError("Email required")
    if any(unicodedata.category(ch) in ("Cc", "Cf", "Cs") for ch in raw):
        raise ValueError("Email contains forbidden control characters")
    email = raw.strip().lower()
    if not 6 <= len(email) <= 254:
        raise ValueError("Email length invalid")
    validator(email)
    return email
