#!/usr/bin/env python3
"""Read-only, fail-closed product identity admission for the VPS factory.

An independently administered, root-owned anchor names the one permitted SKU.
This verifier does not create, advance, release, or sign that anchor. In
particular, a previous handoff digest is not by itself proof of valid QC or
receiver acceptance. All producer paths must opt in before it is a global gate.
"""

import json
import os
from pathlib import Path
import re
import stat


SCHEMA = "saeit.factory.protected-active-product.v1"
LANES = frozenset(("line41", "agri200"))
PRODUCT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
HEX = re.compile(r"^[0-9a-f]{64}$")
FIELDS = frozenset(("schema", "lane", "product_id", "generation", "previous_handoff_sha256"))
MAX_BYTES = 4096


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("F01_PRODUCT_ANCHOR_DUPLICATE_FIELD")
        result[key] = value
    return result


def validate_claim(raw, expected_lane, expected_product):
    """Validate an exact claim without interpreting it as a signed receipt."""
    if expected_lane not in LANES:
        raise ValueError("F01_PRODUCT_LANE_INVALID")
    if not isinstance(expected_product, str) or not PRODUCT_ID.fullmatch(expected_product):
        raise ValueError("F01_PRODUCT_ID_INVALID")
    try:
        claim = json.loads(raw, object_pairs_hook=_unique_pairs)
    except ValueError as exc:
        if str(exc) == "F01_PRODUCT_ANCHOR_DUPLICATE_FIELD":
            raise
        raise ValueError("F01_PRODUCT_ANCHOR_INVALID_JSON") from None
    except (TypeError, UnicodeDecodeError):
        raise ValueError("F01_PRODUCT_ANCHOR_INVALID_JSON") from None
    if not isinstance(claim, dict) or set(claim) != FIELDS:
        raise ValueError("F01_PRODUCT_ANCHOR_FIELDS_INVALID")
    if claim["schema"] != SCHEMA:
        raise ValueError("F01_PRODUCT_ANCHOR_SCHEMA_INVALID")
    if claim["lane"] not in LANES:
        raise ValueError("F01_PRODUCT_ANCHOR_LANE_INVALID")
    product = claim["product_id"]
    if not isinstance(product, str) or not PRODUCT_ID.fullmatch(product):
        raise ValueError("F01_PRODUCT_ANCHOR_PRODUCT_INVALID")
    generation = claim["generation"]
    if type(generation) is not int or not 1 <= generation <= 2**63 - 1:
        raise ValueError("F01_PRODUCT_ANCHOR_GENERATION_INVALID")
    previous = claim["previous_handoff_sha256"]
    if generation == 1:
        if previous is not None:
            raise ValueError("F01_PRODUCT_ANCHOR_FIRST_HANDOFF_INVALID")
    elif not isinstance(previous, str) or not HEX.fullmatch(previous):
        raise ValueError("F01_PRODUCT_ANCHOR_PREVIOUS_HANDOFF_REQUIRED")
    if claim["lane"] != expected_lane or product != expected_product:
        raise ValueError("F01_PRODUCT_ANCHOR_DIFFERENT_ACTIVE_PRODUCT")
    return claim


def _require_root_protected_path(path):
    """A writable ancestor can replace even an otherwise protected key file."""
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise ValueError("F01_PRODUCT_ANCHOR_SYMLINK")
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError("F01_PRODUCT_ANCHOR_NOT_ADMIN_PROTECTED")
        if part == path:
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_BYTES or info.st_nlink != 1:
                raise ValueError("F01_PRODUCT_ANCHOR_FILE_UNSAFE")
        elif not stat.S_ISDIR(info.st_mode):
            raise ValueError("F01_PRODUCT_ANCHOR_PARENT_UNSAFE")


def require_active_product(anchor_path, lane, product_id):
    """Read the operator-protected current SKU; make no filesystem writes."""
    path = Path(anchor_path)
    if not path.is_absolute():
        raise ValueError("F01_PRODUCT_ANCHOR_ABSOLUTE_PATH_REQUIRED")
    _require_root_protected_path(path)
    descriptor = os.open(str(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_mode & 0o022 or not 0 < info.st_size <= MAX_BYTES
                or info.st_nlink != 1):
            raise ValueError("F01_PRODUCT_ANCHOR_FILE_CHANGED")
        data = os.read(descriptor, MAX_BYTES + 1)
        if len(data) != info.st_size:
            raise ValueError("F01_PRODUCT_ANCHOR_READ_INCOMPLETE")
    finally:
        os.close(descriptor)
    return validate_claim(data, lane, product_id)

