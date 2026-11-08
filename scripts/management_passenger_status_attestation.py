#!/usr/bin/env python3
"""One-shot, non-mutating Passenger process-to-Python identity attestation.

Runs on the *cPanel host*, under the unprivileged application account, from
the trusted SSH relay. Passenger status XML is kept in memory, never printed.
Never imports the Django app, reads environment variables, writes files or
starts a Python interpreter chosen from application configuration.
"""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import xml.etree.ElementTree as ET


APP_ROOT = "/home/zomorod2/Saeit"
MAX_STATUS_BYTES = 2 * 1024 * 1024
MAX_APP_PROCESSES = 32


def _result(reason: str, *, groups: int = 0, pids: int = 0,
            matched: int = 0, version: str = "unverified", verified: bool = False) -> dict:
    return {
        "classification": "MANAGEMENT_PASSENGER_PROCESS_IDENTITY_READ_ONLY_V1",
        "reason": reason,
        "matching_application_groups": groups,
        "matching_application_processes": pids,
        "binary_identity_matches": matched,
        "python_version_hint": version,
        "active_interpreter_binary_attested": verified,
        "django_environment_attested": False,
        "production_source_attested": False,
        "migrations_attested": False,
        "backup_restore_attested": False,
        "release_permitted": False,
        "production_mutation": False,
    }


def _version_from_basename(name: str) -> str:
    match = re.fullmatch(r"python(3\.(?:9|10|11|12|13))", name)
    return match.group(1) if match else "unverified"


def _configured_binary(path: str) -> tuple[int, int]:
    # No subprocess, import, read or evaluation of the XML-provided path.
    if not path.startswith("/") or "\x00" in path:
        raise ValueError("configured Python is not absolute")
    details = os.stat(path)
    if not stat.S_ISREG(details.st_mode) or not os.access(path, os.X_OK):
        raise ValueError("configured Python is not executable")
    return details.st_dev, details.st_ino


def _process_binary(pid: int) -> tuple[int, tuple[int, int], str]:
    base = f"/proc/{pid}"
    uid = os.stat(base).st_uid
    details = os.stat(f"{base}/exe")
    name = os.path.basename(os.readlink(f"{base}/exe")).removesuffix(" (deleted)")
    return uid, (details.st_dev, details.st_ino), _version_from_basename(name)


def attest_xml(xml: bytes, *, configured_binary=_configured_binary,
               process_binary=_process_binary, expected_uid: int | None = None) -> dict:
    """Strictly match one app group and its live processes, otherwise deny.

    `configured_binary` and `process_binary` are injectable for offline tests.
    A matched executable is NOT proof of sys.prefix, migrations or app code.
    """
    if not xml or len(xml) > MAX_STATUS_BYTES:
        return _result("status_xml_empty_or_oversized")
    try:
        document = ET.fromstring(xml)
    except ET.ParseError:
        return _result("invalid_passenger_xml")
    if document.tag != "info":
        return _result("unexpected_passenger_xml_root")

    groups = [group for group in document.findall("./supergroups/supergroup/group")
              if group.findtext("./app_root") == APP_ROOT]
    if len(groups) != 1:
        return _result("target_app_missing_or_ambiguous", groups=len(groups))

    group = groups[0]
    configured_python = (group.findtext("./options/python") or "").strip()
    if not configured_python:
        return _result("python_option_missing", groups=1)

    raw_pids = [p.findtext("./pid") for p in group.findall("./processes/process")]
    if not raw_pids:
        return _result("no_live_passenger_process", groups=1)
    if len(raw_pids) > MAX_APP_PROCESSES or any(not re.fullmatch(r"[1-9][0-9]{0,8}", p or "") for p in raw_pids):
        return _result("invalid_or_excessive_process_list", groups=1)
    pids = [int(pid) for pid in raw_pids]
    if len(pids) != len(set(pids)):
        return _result("duplicate_passenger_pid", groups=1)

    try:
        wanted = configured_binary(configured_python)
    except (OSError, ValueError):
        return _result("configured_binary_not_identified", groups=1, pids=len(pids))

    same_binary = 0
    versions = set()
    for pid in pids:
        try:
            uid, binary, version = process_binary(pid)
        except (OSError, ValueError):
            return _result("passenger_process_unreadable", groups=1,
                           pids=len(pids), matched=same_binary)
        if uid != (os.getuid() if expected_uid is None else expected_uid):
            return _result("foreign_uid_process", groups=1,
                           pids=len(pids), matched=same_binary)
        if binary != wanted:
            return _result("configured_python_differs_from_live_process", groups=1,
                           pids=len(pids), matched=same_binary)
        same_binary += 1
        versions.add(version)

    safe_version = next(iter(versions)) if len(versions) == 1 else "unverified"
    return _result("process_binary_matches_passenger_configuration", groups=1,
                   pids=len(pids), matched=same_binary, version=safe_version, verified=True)


def main() -> int:
    try:
        # Never use sudo or --verbose: XML may contain private data; suppress
        # both raw stdout and stderr and emit only bounded boolean evidence.
        completed = subprocess.run(["passenger-status", "--show=xml"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   timeout=12, check=False)
        if completed.returncode != 0:
            result = _result("passenger_status_unavailable_or_denied")
        else:
            result = attest_xml(completed.stdout)
    except (OSError, subprocess.TimeoutExpired):
        result = _result("passenger_status_unavailable_or_denied")
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0 if result["active_interpreter_binary_attested"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
