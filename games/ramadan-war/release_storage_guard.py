#!/usr/bin/env python3
"""Read-only cPanel capacity gate before any Ramadan War release staging.

This script is streamed over SSH stdin. It never creates a file, calls a
payment service, changes a site, or depends on the VPS relay disk being free.
"""
import os
import sys
from pathlib import Path

STAGING_PARENT = Path("/home/zomorod2")
LIVE_GAME = Path("/home/zomorod2/public_html/ramadan-war")
RESERVE_BYTES = 512 * 1024 * 1024


def check_capacity(stage_parent, live_game, payload_bytes, *, reserve_bytes=RESERVE_BYTES,
                   statvfs=os.statvfs, device=None):
    """Reject low-space or unsafe mounts before writing any release bytes."""
    if not isinstance(payload_bytes, int) or not 0 < payload_bytes < (1 << 40):
        raise ValueError("invalid release payload size")
    if not isinstance(reserve_bytes, int) or reserve_bytes < 0:
        raise ValueError("invalid release reserve")
    stage_parent, live_game = Path(stage_parent), Path(live_game)
    for path in (stage_parent, live_game):
        if not path.is_dir() or path.is_symlink():
            raise RuntimeError("release storage directory missing or linked")
    # A linked ancestor of the game path is not a safe release destination.
    for path in (live_game.parent, live_game.parent.parent):
        if path.is_symlink():
            raise RuntimeError("linked release storage ancestor")
    device = device or (lambda p: p.stat().st_dev)
    stage_free = statvfs(stage_parent)
    game_free = statvfs(live_game)
    stage_bytes = stage_free.f_bavail * stage_free.f_frsize
    game_bytes = game_free.f_bavail * game_free.f_frsize
    # Stage incoming payload + original-file backups + atomic temporary writes.
    # On one filesystem, account for all allocations together, not separately.
    if device(stage_parent) == device(live_game):
        if min(stage_bytes, game_bytes) < reserve_bytes + 4 * payload_bytes:
            raise RuntimeError("insufficient shared release filesystem space")
    else:
        if stage_bytes < reserve_bytes + 2 * payload_bytes:
            raise RuntimeError("insufficient staging filesystem space")
        if game_bytes < reserve_bytes + 2 * payload_bytes:
            raise RuntimeError("insufficient live game filesystem space")
    return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: release_storage_guard.py PAYLOAD_BYTES")
    try:
        check_capacity(STAGING_PARENT, LIVE_GAME, int(sys.argv[1]))
    except (ValueError, RuntimeError, OSError) as exc:
        raise SystemExit("RAMADAN_RELEASE_STORAGE=BLOCKED: " + str(exc))
    print("RAMADAN_RELEASE_STORAGE=PASS (read-only; no release staged)", flush=True)
