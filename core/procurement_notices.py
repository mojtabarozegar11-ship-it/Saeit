"""Validated, public, undated procurement notices; never exposes private desk auctions."""
import json
from functools import lru_cache
from pathlib import Path

NOTICE_PATH = Path(__file__).resolve().parent / "data" / "direct_procurement_notices.json"
EXPECTED_PER_KIND = 36
FORBIDDEN_TIME_FIELDS = frozenset({"date", "created_at", "published_at", "starts_at", "ends_at", "deadline"})

@lru_cache(maxsize=1)
def get_public_procurement_notices():
    data = json.loads(NOTICE_PATH.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Unknown procurement notice schema")
    notices = data["notices"]
    if len(notices) != EXPECTED_PER_KIND * 2:
        raise ValueError("Expected exactly 72 procurement notices")
    ids = set()
    grouped = {"supply": [], "equipment": []}
    for notice in notices:
        identifier = notice["id"]
        kind = notice["kind"]
        if kind not in grouped or identifier in ids or not identifier.startswith(("ZM-SUP-", "ZM-EQP-")):
            raise ValueError("Invalid or duplicate procurement notice")
        if FORBIDDEN_TIME_FIELDS.intersection(notice):
            raise ValueError("No date or deadline fields are permitted in undated notices")
        if not notice.get("scope") or not notice.get("special_checks") or notice.get("contact_path") != "/contact/":
            raise ValueError("Incomplete procurement notice")
        ids.add(identifier)
        grouped[kind].append(notice)
    if any(len(items) != EXPECTED_PER_KIND for items in grouped.values()):
        raise ValueError("Exactly 36 notices are required in each kind")
    # Source-of-truth planned numbers follow the last verified live public ad #349.
    # They remain proposals until actual database reservation is completed.
    planned = [item.get("proposed_public_number")
               for kind in ("supply", "equipment") for item in grouped[kind]]
    if planned != list(range(350, 422)):
        raise ValueError("Planned public-ad numbers must be 350..421 in supply-then-equipment order")
    numbering = data.get("proposed_numbering", {})
    if numbering.get("highest_verified_public_number") != 349:
        raise ValueError("The prior live advertisement baseline must be #349")
    return grouped, data["policy"]
