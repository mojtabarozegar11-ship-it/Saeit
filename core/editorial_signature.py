"""Consistent, idempotent attribution for Zomorod Melal reports and news."""

SIGNATURE = "#مجتبی_روزگار"


def has_final_signature(body: str | None) -> bool:
    """Return true only when the final nonempty line is the exact signature."""
    text = (body or "").rstrip()
    return bool(text and text.splitlines()[-1].strip() == SIGNATURE)


def ensure_signed(body: str | None) -> str:
    """Append the exact signature once, preserving all prior editorial text."""
    text = (body or "").rstrip()
    if has_final_signature(text):
        return text
    return f"{text}\n\n{SIGNATURE}" if text else SIGNATURE
