#!/usr/bin/env python3
"""Only read exact owner cPanel filesystem metadata and public HTTP status.

Checks whether the *new*, additive /moj-prop/plan1/ route is currently occupied.
No file bytes, filenames from directory entries, customer records, credentials,
hashes, dumps, writes, HTTP POST, payments or inferred merchant permission.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import urllib.error
import urllib.request

PARENT = Path("/home/zomorod2/mojplaywin.com/moj-prop")
SIDE = "plan1"
URL = "https://mojplaywin.com/moj-prop/plan1/"
STATES = {"safe_absent", "safe_empty_directory",
          "occupied_do_not_replace", "unsafe_or_unavailable"}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def safe_dir(path: Path, uid: int) -> bool:
    try:
        s = path.lstat()
        return (stat.S_ISDIR(s.st_mode)
                and s.st_uid == uid and s.st_mode & 0o022 == 0)
    except OSError:
        return False


def classify(parent: Path = PARENT, uid: int | None = None) -> str:
    uid = os.geteuid() if uid is None else uid
    if not parent.is_absolute() or any(
        not safe_dir(path, uid)
        for path in (parent.parent.parent, parent.parent, parent)
    ):
        return "unsafe_or_unavailable"
    try:
        p = parent / SIDE
        entry = p.lstat()
    except FileNotFoundError:
        return "safe_absent"
    except OSError:
        return "unsafe_or_unavailable"
    if (not stat.S_ISDIR(entry.st_mode) or entry.st_uid != uid
            or entry.st_mode & 0o022):
        return "occupied_do_not_replace"
    try:
        fd = os.open(p, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            opened = os.fstat(fd)
            if (opened.st_dev, opened.st_ino) != (entry.st_dev, entry.st_ino):
                return "unsafe_or_unavailable"
            # Only peek whether any entry exists, never print actual names.
            with os.scandir(fd) as iterator:
                if next(iterator, None) is not None:
                    return "occupied_do_not_replace"
            return "safe_empty_directory"
        finally:
            os.close(fd)
    except OSError:
        return "unsafe_or_unavailable"


def get_http_status() -> int:
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(
        URL, method="GET",
        headers={"User-Agent": "MOJPROP-SIDECAR-DestinationReadOnly/1",
                 "Accept-Encoding": "identity"},
    )
    try:
        with opener.open(req, timeout=12) as response:
            return int(response.getcode())
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except (urllib.error.URLError, OSError, TimeoutError):
        return 0


def inspect(parent: Path = PARENT, getter=get_http_status) -> dict:
    value = classify(parent)
    try:
        code = getter()
    except (OSError, ValueError, TimeoutError):
        code = 0
    return {
        "schema": "mojprop.sidecar.owner_route_vacancy.readonly.v1",
        "route_status": value,
        "public_http_status": code,
        "vacant_for_new_additive_source": value == "safe_absent",
        "read_only": True,
        "existing_home_contact_preserved": True,
        "no_file_data_or_customer_data_read": True,
        "production_release_authorized": False,
        "payment_or_email_sent": False,
    }


def main():
    print("MOJPROP_OWNER_PLAN1_VACANCY_READONLY=" +
          json.dumps(inspect(), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
