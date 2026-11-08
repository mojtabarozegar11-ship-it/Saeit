"""Safe, consistent presentation of Zomorod Melal reports and news."""

import json

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


def safe_news_jsonld(data: object) -> str:
    """Encode JSON-LD for inclusion inside an HTML script element.

    Plain ``json.dumps`` does not escape ``</script>`` in untrusted titles.
    Escaping HTML-sensitive characters preserves JSON values but stops a
    source headline from terminating the non-executable JSON-LD script block.
    """
    encoded = json.dumps(data, ensure_ascii=False)
    return (encoded.replace("&", r"\u0026")
                   .replace("<", r"\u003c")
                   .replace(">", r"\u003e")
                   .replace("\u2028", r"\u2028")
                   .replace("\u2029", r"\u2029"))
