#!/usr/bin/env python3
"""F-01 durable, fail-closed lane reservation shared by all serial factory engines.

A process lock alone does not protect the interval between minute ticks. This
reservation survives process exit and reboot. Each admitted lane MUST separately
enforce one product until signed QC1000 plus receiver acceptance. Other, older
producers must be retired before this is deployed: this module does not control
an executable which has not opted into it.
"""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import tempfile

SCHEMA = "saeit.factory.global-single-production-lane.v1"
LANES = frozenset(("line41", "agri200"))
LOCK_NAME = ".f01-global-production-lane.lock"
STATE_NAME = ".f01-global-production-lane.json"


def _safe_root(value):
    path = Path(value)
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError("F01_GLOBAL_ROOT_MISSING_OR_UNSAFE")
    return path.resolve(strict=True)


def _state(path):
    if path.is_symlink():
        raise RuntimeError("F01_GLOBAL_STATE_SYMLINK")
    if not path.exists():
        return {"schema": SCHEMA, "owner": None, "generation": 0}
    if not path.is_file() or path.stat().st_size > 4096:
        raise RuntimeError("F01_GLOBAL_STATE_UNSAFE")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError, OSError) as exc:
        raise RuntimeError("F01_GLOBAL_STATE_UNREADABLE") from exc
    if (not isinstance(data, dict) or data.get("schema") != SCHEMA
            or data.get("owner") not in LANES | {None}
            or type(data.get("generation")) is not int
            or data["generation"] < 0):
        raise RuntimeError("F01_GLOBAL_STATE_INVALID")
    return data


def _atomic(path, data):
    fd, name = tempfile.mkstemp(prefix=".f01-lane-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(data, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        dirfd = os.open(str(path.parent), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        if os.path.exists(name):
            os.unlink(name)



def _foreign_state(path):
    # Unknown or malformed existing state must never be treated as idle.
    if path.is_symlink():
        raise RuntimeError("F01_FOREIGN_STATE_SYMLINK")
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > 2_000_000:
        raise RuntimeError("F01_FOREIGN_STATE_UNSAFE")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise RuntimeError("F01_FOREIGN_STATE_UNREADABLE") from exc
    if not isinstance(value, dict):
        raise RuntimeError("F01_FOREIGN_STATE_INVALID")
    return value


def _require_foreign_lane_idle(root, lane):
    if lane == "line41":
        other = _foreign_state(root / "production-instructions" /
                               "stage-06" / "strict-serial-active-v1.json")
        if other is not None and (other.get("active_order") is not None
                                  or other.get("all_complete") is not True):
            raise RuntimeError("F01_AGRI200_ORDER_NOT_RELEASED")
    else:
        other = _foreign_state(root / "quality-excellence" / "product-flow" /
                               "active-slots" / "current.json")
        if other is not None:
            active = other.get("active")
            if not isinstance(active, list):
                raise RuntimeError("F01_LINE41_SLOT_UNKNOWN")
            if active:
                raise RuntimeError("F01_LINE41_PRODUCT_NOT_RELEASED")


def reserve_lane(factory_private, lane):
    """Idempotently reserve the one factory lane; never steal a stale claim."""
    if lane not in LANES:
        raise ValueError("F01_GLOBAL_LANE_INVALID")
    root = _safe_root(factory_private)
    path = root / LOCK_NAME
    if path.is_symlink():
        raise RuntimeError("F01_GLOBAL_LOCK_SYMLINK")
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("F01_GLOBAL_RESERVATION_BUSY") from exc
        _require_foreign_lane_idle(root, lane)
        state_path = root / STATE_NAME
        state = _state(state_path)
        if state["owner"] not in (None, lane):
            raise RuntimeError("F01_GLOBAL_OTHER_LANE_RESERVED:" + str(state["owner"]))
        if state["owner"] is None:
            state = {"schema": SCHEMA, "owner": lane,
                     "generation": state["generation"] + 1,
                     "claimed_utc": datetime.now(timezone.utc).isoformat()}
            _atomic(state_path, state)
        return dict(state)
    finally:
        os.close(fd)
