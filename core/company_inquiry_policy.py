"""Dependency-free, deterministic admission policy for Zomorod company CRM.

Protects *one browser session* against accidental repeated submissions and
excessive new requests; this is not a distributed rate limiter. The farm
funnel must only classify server-created farm intake provenance, not a
customer-submitted subject alone. No customer identity is recorded here.
"""
from __future__ import annotations

import re

MAX_NEW_LEADS_PER_SESSION = 6
WINDOW_SECONDS = 60 * 60
REPLAY_SECONDS = 15 * 60
FARM_SUBJECT = "ZM-FARM | درخواست تحلیل اقتصادی مزرعه"
CONSENT_MARKER = "INTAKE_CONSENT_V1"
_FINGERPRINT = re.compile(r"[0-9a-f]{64}\Z")


def _valid(entry, now):
    if type(entry) is not dict or set(entry) != {"fingerprint", "created", "inquiry_id"}:
        return False
    fp, created, inquiry_id = entry["fingerprint"], entry["created"], entry["inquiry_id"]
    return (
        type(fp) is str and _FINGERPRINT.fullmatch(fp) is not None
        and type(created) is int and 0 <= now - created < WINDOW_SECONDS
        and type(inquiry_id) is int and inquiry_id > 0
    )


def clean_history(raw, now):
    """Bound and sanitize saved same-browser records; newest fingerprint wins."""
    if type(now) is not int or now < 0 or type(raw) is not list:
        return []
    used = set()
    result = []
    for entry in reversed(raw[-MAX_NEW_LEADS_PER_SESSION * 4:]):
        if not _valid(entry, now) or entry["fingerprint"] in used:
            continue
        used.add(entry["fingerprint"])
        result.append({"fingerprint": entry["fingerprint"],
                       "created": entry["created"], "inquiry_id": entry["inquiry_id"]})
        if len(result) >= MAX_NEW_LEADS_PER_SESSION:
            break
    return list(reversed(result))


def replay_inquiry_id(history, fingerprint, now):
    """Return a saved CRM row ID only within the short replay window."""
    if type(fingerprint) is not str or _FINGERPRINT.fullmatch(fingerprint) is None:
        return None
    for entry in reversed(clean_history(history, now)):
        if entry["fingerprint"] == fingerprint and now - entry["created"] < REPLAY_SECONDS:
            return entry["inquiry_id"]
    return None


def can_create(history, now):
    return len(clean_history(history, now)) < MAX_NEW_LEADS_PER_SESSION


def add_new(history, fingerprint, now, inquiry_id):
    """Remember only completed DB saves. Fail closed if inputs or quota invalid."""
    if (type(now) is not int or now < 0
            or type(inquiry_id) is not int or inquiry_id <= 0
            or type(fingerprint) is not str or _FINGERPRINT.fullmatch(fingerprint) is None):
        raise ValueError("Invalid persisted inquiry metadata")
    cleaned = clean_history(history, now)
    if len(cleaned) >= MAX_NEW_LEADS_PER_SESSION:
        raise ValueError("Session intake limit reached")
    return cleaned + [{"fingerprint": fingerprint, "created": now, "inquiry_id": inquiry_id}]


def provenance(kind, subject, internal_note):
    """Only one server-stamped CRM service type is eligible for farm funnel."""
    if type(internal_note) is not str:
        return False
    # Staff may append notes on later lines. The original server-generated
    # first line remains the exact intake provenance, never a free-text title.
    initial_stamp = internal_note.split("\n", 1)[0]
    return (
        kind == "commercial" and subject == FARM_SUBJECT
        and initial_stamp.startswith(CONSENT_MARKER + "; confirmed_at=")
        and initial_stamp.endswith("; source=farm")
    )


def normalize_customer_text(value, *, multiline=False):
    """Normalize human-provided text; deny bidi/control spoofing without losing Persian."""
    if type(value) is not str:
        raise ValueError("Invalid customer text")
    value = value.strip()
    if multiline:
        value = value.replace("\r\n", "\n").replace("\r", "\n")
    for ch in value:
        code = ord(ch)
        if (code < 32 and not (multiline and ch in ("\n", "\t"))
                or code == 127 or code == 0x200B
                or 0x202A <= code <= 0x202E or 0x2066 <= code <= 0x2069):
            raise ValueError("Invalid control character in customer text")
    return value if multiline else " ".join(value.split())


def normalize_customer_email(value):
    if type(value) is not str:
        raise ValueError("Invalid customer email")
    local, sep, domain = value.strip().rpartition("@")
    if not sep or not local or not domain:
        raise ValueError("Invalid customer email")
    return local + "@" + domain.lower()


def normalize_optional_phone(value):
    number = normalize_customer_text(value)
    if not number:
        return ""
    if not re.fullmatch(r"\+?[\d\s().-]+", number) or not 7 <= sum(c.isdigit() for c in number) <= 15:
        raise ValueError("Invalid customer phone")
    return number
