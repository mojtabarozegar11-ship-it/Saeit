"""Exact-byte static-only Moj Prop four-value repair proposal; NO file writes.

Requires SHA256 of both owner static file and current public GET to match
before candidate generation. Does not touch the public site, DB, payments,
files or customer records. Any later release requires separately approved
private-file backup + atomic replace + rollback and exact post-deploy HTTP GET.
"""
from __future__ import annotations
import hashlib
import re
from scripts.mojprop_cpanel_horizon_parity_readonly_c125 import classify, EXPECTED, LABELS

ROOT = b'<select id="horizon">'
END = b'</select>'
OPTION = re.compile(rb'<option(?: value="([^"<>]{0,64})")?>([^<>]{1,90})</option>')
MAX_SIZE = 512_000


def plan(original: bytes, expected_live_sha: str) -> tuple[bytes | None, dict]:
    """Make a candidate in memory only. Never infer approval from candidate."""
    evidence = classify(original, expected_live_sha)
    result = {
        "schema": "mojprop.horizon.exact_byte.static_plan.c126.v1",
        "read_only": True,
        "prechange_http_file_parity": evidence["public_http_matches_disk"],
        "candidate_generated": False,
        "replacement_count": 0,
        "original_sha256": None,
        "proposed_sha256": None,
        "only_horizon_value_attributes_modified": False,
        "independent_file_backup_verified": False,
        "post_apply_http_verified": False,
        "production_write_authorized": False,
        "backend_database_or_payment_modified": False,
    }
    if not evidence["surgical_value_only_candidate"] or type(original) is not bytes:
        return None, result
    if len(original) > MAX_SIZE or original.count(ROOT) != 1:
        return None, result
    start = original.index(ROOT) + len(ROOT)
    end = original.find(END, start)
    if end < 0 or original.find(ROOT, start) >= 0:
        return None, result
    section = original[start:end]
    matches = list(OPTION.finditer(section))
    if len(matches) != 4:
        return None, result
    labels = tuple(" ".join(m.group(2).decode("utf-8").split()) for m in matches)
    if labels != LABELS or re.sub(OPTION, b"", section).strip():
        return None, result
    new_section = bytearray()
    last = 0
    for index, match in enumerate(matches):
        if match.group(1) is None:
            # Precisely one bare <option> is amended; label text is untouched.
            new_section += section[last:match.start()]
            new_section += b'<option value="' + EXPECTED[index].encode("ascii") + b'">'
            new_section += match.group(2) + b'</option>'
            last = match.end()
        else:
            new_section += section[last:match.start(1)]
            new_section += EXPECTED[index].encode("ascii")
            last = match.end(1)
    new_section += section[last:]
    candidate = original[:start] + bytes(new_section) + original[end:]
    verify = classify(candidate, hashlib.sha256(candidate).hexdigest())
    if not verify["horizon_values_canonical"] or not verify["option_labels_exact_reviewed"]:
        return None, result
    result.update({
        "candidate_generated": True,
        "replacement_count": 4,
        "original_sha256": hashlib.sha256(original).hexdigest(),
        "proposed_sha256": hashlib.sha256(candidate).hexdigest(),
        "only_horizon_value_attributes_modified": True,
    })
    return candidate, result
