#!/usr/bin/env python3
"""Guarded live Passenger refresh for the already-staged checkout copy correction.

Only updates the genuine MojPlayWin Passenger app restart marker. It does not
change application code, transaction data, settings, customer data or emails.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import pwd
import re
import stat
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import secrets


STAGING = Path("/home/zomorod2/Saeit-staging")
PASSENGER = Path("/home/zomorod2/mojplaywin.com")
STARTUP_SHA256 = "83a5309b8712aed5139dc7630724ac150edfb32db852af347d0444506fab2581"
CHECKOUT_SHA256 = "2b670a724ba607a300ef8caedba468f3ac0200e9c00d88e64fdc565daa6d9e2f"
OLD = "to recover your download"
NEW = "Email recovery on another device is not yet available"


def ensure_target():
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise RuntimeError("WRONG_APP_OWNER")
    if any(not p.is_dir() or p.is_symlink() for p in (STAGING, PASSENGER)):
        raise RuntimeError("INVALID_APP_DIRECTORIES")
    config = PASSENGER / ".htaccess"
    if config.is_symlink() or not config.is_file() or config.stat().st_size > 40000:
        raise RuntimeError("INVALID_PASSENGER_CONFIG")
    app_root = [line.strip().split(maxsplit=1)[1].strip('"\'')
                for line in config.read_text("utf-8", "replace").splitlines()
                if re.fullmatch(r"\s*PassengerAppRoot\s+\S+\s*", line)]
    if app_root != [str(PASSENGER)]:
        raise RuntimeError("UNEXPECTED_PASSENGER_APP_ROOT")
    startup = PASSENGER / "passenger_wsgi.py"
    if startup.is_symlink() or not startup.is_file():
        raise RuntimeError("INVALID_PASSENGER_STARTUP")
    raw = startup.read_bytes()
    if hashlib.sha256(raw).hexdigest() != STARTUP_SHA256 or bytes(str(STAGING), "utf-8") not in raw:
        raise RuntimeError("PINNED_STARTUP_MISMATCH")
    checkout = STAGING / "mpw_commerce/templates/mpw_commerce/product_checkout.html"
    if checkout.is_symlink() or not checkout.is_file():
        raise RuntimeError("INVALID_CHECKOUT")
    raw = checkout.read_bytes()
    if (hashlib.sha256(raw).hexdigest() != CHECKOUT_SHA256 or
            OLD.encode() in raw or NEW.encode() not in raw):
        raise RuntimeError("PINNED_CHECKOUT_MISMATCH")
    marker = PASSENGER / "tmp/restart.txt"
    if (marker.is_symlink() or not marker.is_file() or
            not marker.resolve().is_relative_to(PASSENGER.resolve()) or
            not stat.S_ISREG(marker.stat().st_mode)):
        raise RuntimeError("INVALID_PASSENGER_RESTART_MARKER")
    return marker


def public_text():
    nonce = secrets.token_hex(8)
    req = Request("https://mojplaywin.com/commerce/book/72/?mpw_live_refresh=" + nonce,
                  headers={"Cache-Control": "no-cache", "Pragma": "no-cache",
                           "User-Agent": "MPW-Guarded-Live-Refresh/1.0"})
    try:
        with urlopen(req, timeout=9) as resp:
            if resp.status != 200:
                return "not_200"
            content = resp.read(250000).decode("utf-8", "replace")
            if NEW in content and OLD not in content:
                return "new"
            if OLD in content:
                return "old"
            return "unknown"
    except (HTTPError, URLError, TimeoutError, OSError):
        return "unavailable"


def main():
    if len(sys.argv) != 2 or sys.argv[1] != "activate":
        raise RuntimeError("INVALID_OPERATION")
    marker = ensure_target()
    initial = public_text()
    if initial == "new":
        print("MPW_PASSENGER_REFRESH=ALREADY_LIVE;EMAILS=0;PAYMENTS=0;DB_WRITES=0",
              flush=True)
        return
    if initial != "old":
        raise RuntimeError("PUBLIC_PRECHECK_UNEXPECTED_" + initial)
    marker.touch()
    # Passenger may briefly be unavailable during graceful worker replacement.
    observed = []
    for attempt in range(8):
        if attempt:
            time.sleep(3)
        state = public_text()
        observed.append(state)
        if state == "new":
            second = public_text()
            observed.append(second)
            if second == "new":
                print("MPW_PASSENGER_REFRESH=PASS;PUBLIC_CHECKOUT_NEW_COPY=2_OF_2;"
                      "EMAILS=0;PAYMENTS=0;DB_WRITES=0", flush=True)
                return
    print("MPW_PASSENGER_REFRESH=NOT_VERIFIED;OBSERVATIONS=" + ",".join(observed),
          flush=True)
    raise RuntimeError("PUBLIC_COPY_DID_NOT_REFRESH")


if __name__ == "__main__":
    main()
