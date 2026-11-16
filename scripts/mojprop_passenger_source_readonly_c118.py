#!/usr/bin/env python3
"""Owner-only C118 source identity check, never a live-worker/runtime claim.

Reads only one fixed Passenger WSGI file and five fixed source file metadata.
No application import, SQL, HTTP, exec, subprocess, SSH, file write or PII.
Outputs a bounded, schema-versioned public boolean/digest diagnostic.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat

ROOT = Path("/home/zomorod2/Saeit-staging")
WEBROOT = Path("/home/zomorod2/mojplaywin.com")
ENTRY = WEBROOT / "passenger_wsgi.py"
STAGE_LITERAL = "/home/zomorod2/Saeit-staging"
MAX_ENTRY_BYTES = 32768
SOURCE_FILES = (
    "core/mojprop_views.py",
    "core/mojprop_receipts.py",
    "core/mojprop_accessible_intake.py",
    "config/urls.py",
    "core/management/commands/mojprop_sales_action_queue.py",
)


def source_code_signals(blob: bytes) -> dict:
    """Pure parse, not evaluation; comments cannot spoof AST path literals."""
    if type(blob) is not bytes or not 1 <= len(blob) <= MAX_ENTRY_BYTES:
        raise ValueError("bounded passenger source required")
    # Python 3.8's parser can raise MemoryError on ~1000 nested brackets even
    # with a 3 KiB input. Bound nesting first, before invoking compile()/AST.
    depth = 0
    for byte in blob:
        if byte in (40, 91, 123):  # ( [ {
            depth += 1
            if depth > 128:
                raise ValueError("passenger source nesting too deep")
        elif byte in (41, 93, 125):  # ) ] }
            depth = max(0, depth - 1)
    try:
        tree = ast.parse(blob.decode("utf-8"), mode="exec")
    except (SyntaxError, UnicodeDecodeError, ValueError, RecursionError,
            MemoryError) as exc:
        raise ValueError("invalid passenger source") from exc
    declared = False
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == "application"
                   for target in targets):
                declared = True
        if isinstance(node, ast.ImportFrom) and any(
                alias.asname == "application" or
                (alias.name == "application" and alias.asname is None)
                for alias in node.names
        ):
            declared = True
    strings = [node.value for node in ast.walk(tree)
               if isinstance(node, ast.Constant) and type(node.value) is str]
    return {
        "entry_ast_parsed": True,
        "application_binding_declaration_found": declared,
        "staging_path_literal_found": STAGE_LITERAL in strings,
        "entry_sha256": hashlib.sha256(blob).hexdigest(),
    }


def _owned_safe_directory(path: Path) -> bool:
    """Never follow a directory symlink or trust an attacker-writable parent."""
    try:
        info = path.lstat()
    except OSError:
        return False
    return (stat.S_ISDIR(info.st_mode)
            and info.st_uid == os.geteuid()
            and not (info.st_mode & 0o022))


def _owned_safe_file(path: Path, *, root: Path) -> str:
    """Inspect fixed names only; deny symlinks and mutable ancestor dirs."""
    if path == root or root not in path.parents:
        return "unsafe"
    cursor = path.parent
    while cursor != root:
        if (cursor == cursor.parent or root not in cursor.parents
                or not _owned_safe_directory(cursor)):
            return "unsafe"
        cursor = cursor.parent
    if not _owned_safe_directory(root):
        return "unsafe"
    try:
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_mode & 0o022 or info.st_nlink != 1):
            return "unsafe"
        return "present"
    except FileNotFoundError:
        return "missing"
    except OSError:
        return "unavailable"


def report() -> dict:
    out = {
        "schema": "mojprop.passenger.source_identity.readonly.c118.v1",
        "read_only": True,
        "owner_identity_verified": False,
        "staging_root_safe": False,
        "webroot_safe": False,
        "entry_file_state": "unavailable",
        "entry_ast_parsed": False,
        "application_binding_declaration_found": False,
        "staging_path_literal_found": False,
        "entry_sha256": None,
        "staging_sources": {p: "unavailable" for p in SOURCE_FILES},
        "runtime_worker_identity_proven": False,
        "full_db_app_media_restore_proven": False,
        "crm_lead_created": False,
        "email_sent": False,
        "payment_created": False,
        "deploy_authorized": False,
    }
    try:
        if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
            return out
        out["owner_identity_verified"] = True
        if not (_owned_safe_directory(ROOT) and _owned_safe_directory(WEBROOT)):
            return out
        out["staging_root_safe"] = True
        out["webroot_safe"] = True
        out["staging_sources"] = {
            name: _owned_safe_file(ROOT / name, root=ROOT)
            for name in SOURCE_FILES
        }
        state = _owned_safe_file(ENTRY, root=WEBROOT)
        out["entry_file_state"] = state
        if state != "present":
            return out
        size = ENTRY.stat().st_size
        if not 1 <= size <= MAX_ENTRY_BYTES:
            out["entry_file_state"] = "unsafe"
            return out
        data = ENTRY.read_bytes()
        try:
            result = source_code_signals(data)
        except ValueError:
            out["entry_file_state"] = "unsafe"
            return out
        out.update(result)
    except (OSError, ValueError, KeyError):
        pass
    return out


if __name__ == "__main__":
    print("MOJPROP_C118_PASSENGER_SOURCE_READONLY=" +
          json.dumps(report(), sort_keys=True, separators=(",", ":")))
