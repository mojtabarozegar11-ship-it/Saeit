#!/usr/bin/env python3
"""Read-only, redacted cTrader CLI account and running-cBot preflight.

This program NEVER launches, stops, modifies, or trades. It only calls the
documented 'accounts' (batch), then 'cbots', 'positions' and
'orders' (quick read-only interactive) commands.
Production use requires a manually provisioned, owner-approved *DEMO*
account config. No personal identifiers or CLI raw output are printed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

SCHEMA = "mojtaba.bot.ai.ctrader-cli-readonly-preflight.v1"
MAX_CONFIG_BYTES = 4096
MAX_CLI_OUTPUT_BYTES = 512_000
TIMEOUT_SECONDS = 25
SAFE_ATOM = re.compile(r"^[A-Za-z0-9_.@+-]{2,128}$")
SAFE_BROKER = re.compile(r"^[A-Za-z0-9 _.-]{2,80}$")
SAFE_ALIAS = re.compile(r"^[A-Za-z0-9_-]{3,40}$")
SAFE_FILENAME = re.compile(r"^[A-Za-z0-9_.-]{1,90}$")


class PreflightError(ValueError):
    """A blocker with a fixed, safe diagnostic code (never raw CLI text)."""


def _private_file(path: Path, *, max_size: int) -> bytes:
    """Reject symlinks, hardlinks and world-visible data before reading."""
    if not path.is_absolute() or path.is_symlink():
        raise PreflightError("private_file_path_invalid")
    if not path.parent.is_dir() or any(
        folder.is_symlink() for folder in (path.parent, *path.parent.parents)
    ):
        raise PreflightError("private_directory_untrusted")
    if stat.S_IMODE(path.parent.stat().st_mode) & 0o077:
        raise PreflightError("private_directory_not_0700")
    try:
        with os.fdopen(os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)), "rb") as f:
            info = os.fstat(f.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or not 0 < info.st_size <= max_size
                    or stat.S_IMODE(info.st_mode) & 0o077):
                raise PreflightError("private_file_not_0600")
            data = f.read(max_size + 1)
            if len(data) != info.st_size:
                raise PreflightError("private_file_changed_during_read")
    except OSError as exc:
        raise PreflightError("private_file_unavailable") from exc
    return data


def _no_duplicate_keys(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise PreflightError("config_duplicate_key")
        seen[key] = value
    return seen


def read_config(config_path: Path) -> dict:
    raw = _private_file(config_path, max_size=MAX_CONFIG_BYTES)
    try:
        cfg = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PreflightError("config_not_json") from exc
    required = {
        "schema_version", "ctid", "demo_account", "account_alias",
        "broker", "password_file",
    }
    if not isinstance(cfg, dict) or set(cfg) != required or cfg["schema_version"] != 1:
        raise PreflightError("config_schema_invalid")
    if not isinstance(cfg["ctid"], str) or not SAFE_ATOM.fullmatch(cfg["ctid"]):
        raise PreflightError("ctid_invalid")
    account = cfg["demo_account"]
    if not isinstance(account, str) or not account.isascii() or not account.isdigit():
        raise PreflightError("demo_account_invalid")
    if not 4 <= len(account) <= 20:
        raise PreflightError("demo_account_invalid")
    if not isinstance(cfg["account_alias"], str) or not SAFE_ALIAS.fullmatch(cfg["account_alias"]):
        raise PreflightError("account_alias_invalid")
    if not isinstance(cfg["broker"], str) or not SAFE_BROKER.fullmatch(cfg["broker"]):
        raise PreflightError("broker_invalid")
    name = cfg["password_file"]
    if (not isinstance(name, str) or not SAFE_FILENAME.fullmatch(name)
            or name in {".", ".."}):
        raise PreflightError("password_filename_invalid")
    password_path = config_path.parent / name
    # Deliberately never store or print the password. The binary reads it.
    _private_file(password_path, max_size=4096)
    cfg["password_path"] = str(password_path)
    return cfg


def _unique_cli_keys(pairs):
    # Silent last-key-wins parsing can turn a denied account or a failed
    # broker query into an apparently successful list. Reject duplicates at
    # *every* JSON nesting level (including individual account records).
    values = {}
    for key, value in pairs:
        if key in values:
            raise PreflightError("cli_response_duplicate_key")
        values[key] = value
    return values


def _response(stdout: str, *, kind: str):
    if not isinstance(stdout, str) or len(stdout.encode("utf-8")) > MAX_CLI_OUTPUT_BYTES:
        raise PreflightError(kind + "_output_exceeded")
    try:
        doc = json.loads(
            stdout, object_pairs_hook=_unique_cli_keys,
            parse_constant=lambda _: (_ for _ in ()).throw(
                PreflightError("cli_response_nonfinite_value")
            ),
        )
    except (ValueError, TypeError) as exc:
        raise PreflightError(kind + "_output_not_json") from exc
    if isinstance(doc, list):
        rows = doc
    elif isinstance(doc, dict):
        # Some versions wrap a list with metadata. An explicit failure
        # marker always overrides that list, regardless of exit code.
        if (doc.get("success") is False or doc.get("ok") is False
                or doc.get("error") not in (None, "")
                or doc.get("errors") not in (None, "", [])):
            raise PreflightError(kind + "_cli_reported_failure")
        rows = doc.get(kind)
        if not isinstance(rows, list):
            raise PreflightError(kind + "_output_schema_unrecognized")
    else:
        raise PreflightError(kind + "_output_schema_unrecognized")
    if len(rows) > 2000 or not all(isinstance(row, dict) for row in rows):
        raise PreflightError(kind + "_output_untrusted_rows")
    return rows


def _demo_bound(rows: list[dict], account: str, broker: str) -> bool:
    """Accept only an explicit, unambiguous account identity + isLive:false."""
    matches = []
    for row in rows:
        # traderLogin is the displayed account ID in Spotware's official
        # Open API model; accountId may instead denote an internal cTID ID.
        # Do not accept a row where login aliases disagree.
        login_fields = (
            "traderLogin", "accountNumber", "login", "account", "accountId",
        )
        present = [
            str(row[key]) for key in login_fields
            if key in row and isinstance(row[key], (int, str))
            and not isinstance(row[key], bool)
        ]
        if account not in present:
            continue
        specific = [
            str(row[key]) for key in
            ("traderLogin", "accountNumber", "login", "account")
            if key in row and isinstance(row[key], (int, str))
            and not isinstance(row[key], bool)
        ]
        if specific and any(value != account for value in specific):
            raise PreflightError("account_alias_identity_conflict")
        # Broker names may have different JSON aliases across versions,
        # but contradictory aliases must not be silently accepted.
        names = [
            row[key] for key in ("brokerName", "broker", "brokerTitleShort")
            if key in row
        ]
        if (not names or not all(
            isinstance(name, str) and name.casefold() == broker.casefold()
            for name in names
        )):
            raise PreflightError("broker_identity_not_verified")
        if row.get("isLive") is not False:
            raise PreflightError("demo_identity_not_explicit")
        matches.append(row)
    return len(matches) == 1


def _running_cbots(rows: list[dict]) -> int:
    """Return a count only for unambiguously identified running instances."""
    seen = set()
    for row in rows:
        identifier = row.get("instanceId", row.get("id"))
        if isinstance(identifier, bool) or not isinstance(identifier, (str, int)):
            raise PreflightError("cbots_instance_id_not_verified")
        value = str(identifier)
        if not value or len(value) > 100 or value in seen:
            raise PreflightError("cbots_instance_duplicate_or_invalid")
        seen.add(value)
    return len(rows)


def run_readonly(config_path: Path, *, cli_binary: str = "ctrader-cli",
                 runner=subprocess.run) -> dict:
    cfg = read_config(config_path)
    binary = shutil.which(cli_binary)
    if not binary or not Path(binary).is_file():
        raise PreflightError("ctrader_cli_not_installed")
    base = [
        "--ctid=" + cfg["ctid"],
        "--pwd-file=" + cfg["password_path"],
        "--account=" + cfg["demo_account"],
        "--broker=" + cfg["broker"],
    ]
    commands = (
        ("accounts", [binary, "accounts", *base]),
        ("cbots", [binary, "cbots", *base, "-q"]),
        ("positions", [binary, "positions", *base, "-q"]),
        ("orders", [binary, "orders", *base, "-q"]),
    )
    output = {}
    digests = {}
    for kind, argv in commands:
        # NEVER allow caller-controlled verbs or trading commands.
        if argv[1] not in ("accounts", "cbots", "positions", "orders"):
            raise PreflightError("disallowed_cli_verb")
        try:
            completed = runner(
                argv, capture_output=True, text=True,
                timeout=TIMEOUT_SECONDS, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PreflightError(kind + "_cli_unavailable") from exc
        if completed.returncode != 0:
            raise PreflightError(kind + "_cli_rejected")
        rows = _response(completed.stdout, kind=kind)
        # Never inspect positions or orders on an unverified or LIVE
        # account. Reject immediately after the first identity response.
        if kind == "accounts" and not _demo_bound(
            rows, cfg["demo_account"], cfg["broker"]
        ):
            raise PreflightError("demo_account_binding_absent_or_ambiguous")
        output[kind] = rows
        digests[kind] = hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest()
    count = _running_cbots(output["cbots"])
    return {
        "schema": SCHEMA,
        "owner": "mojtaba-bot-ai",
        "read_only": True,
        "account_alias": cfg["account_alias"],
        "cli_demo_account_identity_confirmed": True,
        "observed_running_cbot_count": count,
        "observed_open_position_count": len(output["positions"]),
        "observed_pending_order_count": len(output["orders"]),
        "account_exposure_reconciled_for_new_order": False,
        "multiple_cli_cbot_instances_detected": count > 1,
        "single_runtime_instance_independently_attested": False,
        "cloud_and_external_process_census_verified": False,
        "live_orders_submitted_by_this_probe": 0,
        "orders_placed_by_this_probe": 0,
        "trading_release_authorized": False,
        "real_revenue_verified": False,
        "raw_credentials_or_account_number_emitted": False,
        "redacted_source_sha256": digests,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--cli", default="ctrader-cli")
    args = parser.parse_args(argv)
    try:
        result = run_readonly(args.config, cli_binary=args.cli)
    except PreflightError as exc:
        print(json.dumps({
            "schema": SCHEMA, "status": "blocked", "reason": str(exc),
            "trading_release_authorized": False,
            "cli_demo_account_identity_confirmed": False,
            "single_runtime_instance_independently_attested": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
