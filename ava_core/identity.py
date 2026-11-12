"""Compatibility exports and identity validation for the only bot."""

from mojtaba_identity import BOT_ID


def validate_owner_id(owner_id: str) -> str:
    """Reject ambiguous, escaped or control-bearing tenant identifiers.

    The host still must authenticate ownership; syntax validation alone is not
    an authentication mechanism. No implicit case folding or coercion.
    """
    if (not isinstance(owner_id, str) or not owner_id
            or owner_id != owner_id.strip()
            or "\\" in owner_id
            or any(ord(char) < 32 or ord(char) == 127 for char in owner_id)):
        raise ValueError("owner_id must be a canonical single-line identifier")
    return owner_id
