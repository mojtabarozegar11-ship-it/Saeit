"""Owner-level permanent publishing exclusions.

Never transmit a post to the expressly excluded Instagram profile.
Public URL / numeric Graph IDs are not interchangeable: missing identity binds
fail closed. This function has no external network effects.
"""
import re
from urllib.parse import unquote, urlsplit

from .adapters import Blocked

EXCLUDED_INSTAGRAM_HANDLE = "dr.mojtaba.rozegar"


def normalized_handle(value):
    if not isinstance(value, str):
        return ""
    value = unquote(value).strip().casefold().lstrip("@")
    return re.sub(r"[^a-z0-9]", "", value)


def assert_destination_allowed(account):
    """Reject the excluded Instagram page, even with outbound globally enabled.

    Instagram Graph often publishes via opaque numeric page IDs. Therefore
    require an explicit HTTPS instagram.com/<handle> profile identity in the
    verified account registry; without it, no reliable exclusion is possible.
    """
    if not isinstance(account, dict):
        raise Blocked("Invalid destination")
    if account.get("platform") != "instagram":
        return
    destination = account.get("destination", "")
    url = account.get("public_url", "")
    if not isinstance(destination, str) or not isinstance(url, str):
        raise Blocked("Instagram destination identity missing")
    value = urlsplit(url)
    if (value.scheme != "https" or value.hostname not in
        ("instagram.com", "www.instagram.com") or value.username or
        value.password or value.port or value.query or value.fragment):
        raise Blocked("Instagram public profile proof missing")
    path = value.path.strip("/")
    if not path or "/" in path:
        raise Blocked("Instagram exact profile path required")
    known_handle = normalized_handle(path)
    forbidden = normalized_handle(EXCLUDED_INSTAGRAM_HANDLE)
    if not known_handle or known_handle == forbidden:
        raise Blocked("Owner has permanently forbidden this Instagram page")
    if normalized_handle(destination) == forbidden:
        raise Blocked("Owner has permanently forbidden this Instagram page")
    if destination.startswith("@") and normalized_handle(destination) != known_handle:
        raise Blocked("Instagram destination/profile identity mismatch")
    if not destination:
        raise Blocked("Instagram destination missing")
