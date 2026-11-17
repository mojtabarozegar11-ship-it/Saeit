#!/usr/bin/env python3
"""Read-only cause classifier for cPanel Quota UAPI owner-context failures.

Run via existing owner-authored factory VPS -> pinned cPanel SSH relay.
Only two fixed Quota get_quota_info API reads; no user-controlled commands,
database reads, writes, credentials, raw stdout/stderr or filesystem changes.
This cannot prove space, independent restore, live Passenger or release safety.
"""
from __future__ import annotations

import json
import os
import pwd
import shutil
import stat
import subprocess
from pathlib import Path

ACCOUNT = "zomorod2"
HOME = Path("/home/zomorod2")
UAPI = Path("/usr/local/cpanel/bin/uapi")
# The login shell might expose a user-safe uapi wrapper outside cPanel's
# conventional binary location (e.g. a hosting cage). No arbitrary PATH
# command is executed: only this explicit allowlist of regular executables.
BINARY_CANDIDATES = (
    ("cpanel_standard", UAPI),
    ("usr_local_bin", Path("/usr/local/bin/uapi")),
    ("usr_bin", Path("/usr/bin/uapi")),
    ("bin", Path("/bin/uapi")),
)
ENV = {"LC_ALL": "C", "PATH": "/usr/bin:/bin:/usr/local/bin",
       "HOME": str(HOME), "USER": ACCOUNT, "LOGNAME": ACCOUNT}
COMMANDS = (
    (str(UAPI), "--output=json", "--user=" + ACCOUNT, "Quota", "get_quota_info"),
    (str(UAPI), "--output=json", "Quota", "get_quota_info"),
)
OUTCOME_CODES = {
    "not_run", "program_missing", "timeout", "os_error", "nonzero_json",
    "nonzero_nonjson", "zero_nonjson", "uapi_status_denied",
    "uapi_json_unrecognized", "uapi_data_present", "uapi_data_absent",
}


def _public_error_class(body: object) -> str:
    """Fixed vocabulary only; never disclose cPanel error messages."""
    if type(body) is not dict:
        return "unknown"
    errors = body.get("errors")
    if type(errors) is not list:
        errors = body.get("result", {}).get("errors", []) if type(body.get("result")) is dict else []
    if type(errors) is not list:
        return "unknown"
    cleaned = " ".join(x.lower() for x in errors if type(x) is str)[:512]
    if any(x in cleaned for x in ("not permitted", "permission", "unauthorized", "privilege", "access denied")):
        return "permission"
    if any(x in cleaned for x in ("unknown module", "method not found", "does not exist", "invalid module")):
        return "unsupported_api"
    if any(x in cleaned for x in ("quota", "disabled", "unavailable", "not enabled")):
        return "quota_unavailable"
    return "other" if cleaned else "unknown"


def _quota_flag_class(value):
    if value is True or value is False:
        return "boolean"
    if type(value) is int:
        return "int_1" if value == 1 else ("int_0" if value == 0 else "int_other")
    if type(value) is str:
        return "string_1" if value == "1" else ("string_0" if value == "0" else "string_other")
    return "other"


def _quota_number_class(value):
    from decimal import Decimal, InvalidOperation
    if type(value) not in (int, float, str):
        return "invalid"
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            return "invalid"
        return "negative" if number < 0 else ("zero" if number == 0 else "positive")
    except (InvalidOperation, ValueError):
        return "invalid"


def _quota_shapes(data):
    # ONLY fixed type/threshold classes. No amounts, emails or raw API fields.
    names = ("under_quota_overall", "under_megabyte_limit", "under_inode_limit")
    quantities = ("megabyte_limit", "megabytes_remain", "inode_limit", "inodes_remain")
    return {
        "flags": {name: (_quota_flag_class(data[name]) if name in data else "missing")
                  for name in names},
        "quantities": {name: (_quota_number_class(data[name]) if name in data else "missing")
                       for name in quantities},
    }


def classify(argv: tuple[str, ...], *, runner=subprocess.run) -> dict:
    """Only bounded status fields; output payloads remain private."""
    result = {"outcome": "not_run", "exit_nonzero": None,
              "json_response": False, "uapi_status_ok": False,
              "data_object_present": False, "error_class": "unknown"}
    try:
        done = runner(list(argv), env=dict(ENV), capture_output=True,
                      text=True, check=False, timeout=12)
    except FileNotFoundError:
        result["outcome"] = "program_missing"
        return result
    except subprocess.TimeoutExpired:
        result["outcome"] = "timeout"
        return result
    except (OSError, subprocess.SubprocessError):
        result["outcome"] = "os_error"
        return result
    result["exit_nonzero"] = done.returncode != 0
    # JSON is parsed only to classify result shape; no raw API output escapes.
    stdout = done.stdout if type(done.stdout) is str else ""
    if len(stdout) > 16384:
        result["outcome"] = "nonzero_nonjson" if result["exit_nonzero"] else "zero_nonjson"
        return result
    try:
        body = json.loads(stdout)
    except (ValueError, TypeError):
        result["outcome"] = "nonzero_nonjson" if result["exit_nonzero"] else "zero_nonjson"
        return result
    result["json_response"] = True
    result["error_class"] = _public_error_class(body)
    if type(body) is not dict or type(body.get("result")) is not dict:
        result["outcome"] = "nonzero_json" if result["exit_nonzero"] else "uapi_json_unrecognized"
        return result
    inner = body["result"]
    result["uapi_status_ok"] = inner.get("status") == 1
    result["data_object_present"] = type(inner.get("data")) is dict
    if result["data_object_present"]:
        result["quota_shape"] = _quota_shapes(inner["data"])
    if result["exit_nonzero"]:
        result["outcome"] = "nonzero_json"
    elif not result["uapi_status_ok"]:
        result["outcome"] = "uapi_status_denied"
    elif result["data_object_present"]:
        result["outcome"] = "uapi_data_present"
    else:
        result["outcome"] = "uapi_data_absent"
    return result


def _trusted_candidate(path: Path) -> tuple[bool, bool]:
    try:
        meta = path.lstat()
        regular = stat.S_ISREG(meta.st_mode) and not stat.S_ISLNK(meta.st_mode)
        return regular, bool(regular and os.access(path, os.X_OK))
    except OSError:
        return False, False


def main() -> None:
    try:
        owner_ok = pwd.getpwuid(os.geteuid()).pw_name == ACCOUNT
    except (KeyError, OSError):
        owner_ok = False
    binary_status = {
        code: _trusted_candidate(path) for code, path in BINARY_CANDIDATES
    }
    uapi_regular, uapi_executable = binary_status["cpanel_standard"]
    available = [code for code, _ in BINARY_CANDIDATES if binary_status[code][1]]
    login_path_hit = shutil.which("uapi")
    login_path_code = next(
        (code for code, path in BINARY_CANDIDATES
         if login_path_hit and str(path) == login_path_hit),
        "other" if login_path_hit else "none",
    )
    try:
        home_meta = HOME.lstat()
        home_trusted = (stat.S_ISDIR(home_meta.st_mode)
                        and not stat.S_ISLNK(home_meta.st_mode)
                        and home_meta.st_uid == os.geteuid())
    except OSError:
        home_trusted = False
    probes = []
    selected = next(
        ((code, path) for code, path in BINARY_CANDIDATES
         if binary_status[code][1]),
        None,
    )
    if owner_ok and home_trusted and selected:
        # Fixed UAPI operations; the only substitution is a reviewed
        # executable path from BINARY_CANDIDATES.
        probes = [
            classify((str(selected[1]),) + command[1:])
            for command in COMMANDS
        ]
    report = {
        "schema": "mojprop.cpanel.uapi_cause.readonly.v1",
        "read_only": True,
        "owner_verified": owner_ok,
        "home_owner_verified": home_trusted,
        "uapi_regular_file": uapi_regular,
        "uapi_executable": uapi_executable,
        "available_binary_ids": available,
        "login_path_binary_id": login_path_code,
        "selected_binary_id": selected[0] if selected else "none",
        "probes": probes,
        "capacity_confirmed": False,
        "db_restore_executed": False,
        "passenger_isolation_proven": False,
        "payment_collected": False,
        "production_deploy_authorized": False,
    }
    assert all(p["outcome"] in OUTCOME_CODES for p in probes)
    print("MOJPROP_UAPI_CAUSE_C111=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
