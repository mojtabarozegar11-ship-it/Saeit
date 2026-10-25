#!/usr/bin/env python3
"""Fail-closed owner-order exclusion for legacy shared agricultural-stage crons.

Only an authentic 200-order scope can be excluded from those shared workers.
Other-factory work orders remain eligible for their existing minute schedules.
"""
import json
from pathlib import Path
import re


def owner_agri200_ids(root):
    private = Path(root)
    area = private / "production-instructions"
    path = area / "owner-agri200-p0-index.json"
    if (private.is_symlink() or area.is_symlink() or path.is_symlink()
            or not path.is_file() or not 0 < path.stat().st_size <= 100_000):
        raise RuntimeError("STRICT_SERIAL_EXCLUSION_INDEX_UNSAFE")
    record = json.loads(path.read_text(encoding="utf8"))
    ids = record.get("order_ids_ranked")
    if (record.get("topic_count") != 200 or not isinstance(ids, list)
            or len(ids) != 200 or len(set(ids)) != 200
            or any(not isinstance(item, str) or
                   re.fullmatch(r"WO-[0-9]{8}", item) is None for item in ids)):
        raise RuntimeError("STRICT_SERIAL_EXCLUSION_INDEX_INVALID")
    return set(ids)
