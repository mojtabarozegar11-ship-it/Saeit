#!/usr/bin/env python3
"""S-01 R22: strictly offline, read-only release diagnostics.

No SSH, network, database, factory, order, payment, or deployment actions.
No source contents or private path values are emitted in the JSON report.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile

SOURCE_MAX = 2 * 1024 * 1024
ARCHIVE_MAX = 64 * 1024 * 1024
MEMBER_MAX = 8 * 1024 * 1024
ARCHIVE_ENTRIES_MAX = 10000
ALLOWED_TREES = frozenset({"company_messaging", "company_marketing", "enterprise_portal", "ecosystem_hub", "config"})
EXECUTABLE_EXTENSIONS = frozenset({".py", ".pyc", ".pth", ".so", ".sh", ".php"})


def sha(data):
    return hashlib.sha256(data).hexdigest()


def regular_bytes(path, max_bytes=SOURCE_MAX):
    """Read a local owned, single-link regular file, rejecting ancestor symlinks."""
    raw = os.fspath(path)
    if not os.path.isabs(raw) or any(x in (".", "..", "") for x in raw.split("/")[1:]):
        raise ValueError("UNSAFE_ABSOLUTE_PATH")
    parts = raw.split("/")[1:]
    dirfd = fd = None
    try:
        dirfd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        for part in parts[:-1]:
            newfd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dirfd)
            os.close(dirfd)
            dirfd = newfd
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dirfd)
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or before.st_uid != os.getuid() or not 0 < before.st_size <= max_bytes):
            raise ValueError("UNSAFE_SOURCE_FILE")
        with os.fdopen(os.dup(fd), "rb") as stream:
            data = stream.read(max_bytes + 1)
        after = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        if len(data) != before.st_size or any(getattr(before, f) != getattr(after, f) for f in fields):
            raise ValueError("SOURCE_CHANGED_DURING_READ")
        return data
    finally:
        if fd is not None:
            os.close(fd)
        if dirfd is not None:
            os.close(dirfd)


def validate_pin(pin):
    if not re.fullmatch(r"[0-9a-f]{64}", pin):
        raise ValueError("INVALID_SHA256_PIN")


def ast_nodes(data):
    try:
        parsed = ast.parse(data)
    except (SyntaxError, UnicodeError, ValueError, TypeError):
        raise ValueError("SOURCE_SYNTAX_INVALID") from None
    return [(type(n).__name__, sha(ast.dump(n, include_attributes=False).encode())) for n in parsed.body]


def checkout(current, approved, pin):
    validate_pin(pin)
    if Path(current).suffix != ".py" or Path(approved).suffix != ".py":
        raise ValueError("SOURCE_NOT_PYTHON")
    old = regular_bytes(approved)
    new = regular_bytes(current)
    if sha(old) != pin:
        raise ValueError("APPROVED_REFERENCE_PIN_MISMATCH")
    a, b = ast_nodes(old), ast_nodes(new)
    differences = [{"index": i, "approved_kind": a[i][0] if i < len(a) else "ABSENT",
                    "current_kind": b[i][0] if i < len(b) else "ABSENT"}
                   for i in range(max(len(a), len(b)))
                   if i >= len(a) or i >= len(b) or a[i] != b[i]]
    first = next((i for i, (x, y) in enumerate(zip(old, new)) if x != y), min(len(old), len(new)))
    return {"kind": "CHECKOUT_SOURCE_OFFLINE", "status": "PIN_MATCH" if old == new else
            "FORMAT_ONLY_DRIFT" if not differences else "SEMANTIC_DRIFT",
            "approved_sha256": pin, "observed_sha256": sha(new), "first_different_byte": first,
            "top_level_changes": differences[:30], "top_level_change_count": len(differences),
            "top_level_changes_truncated": len(differences) > 30,
            "live_checkout_verified": False, "safe_to_deploy": False}


def office_stage(stage, pin):
    validate_pin(pin)
    raw = os.fspath(stage)
    if not os.path.isabs(raw) or any(x in (".", "..", "") for x in raw.split("/")[1:]):
        raise ValueError("UNSAFE_STAGE_PATH")
    stage = Path(raw)
    archive = regular_bytes(str(stage / "package.tar"), ARCHIVE_MAX)
    if sha(archive) != pin:
        raise ValueError("PACKAGE_PIN_MISMATCH")
    code = stage / "code"
    if not code.is_dir() or code.is_symlink():
        raise ValueError("STAGE_CODE_UNSAFE")
    seen, files, total = set(), set(), 0
    import io
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
        for i, member in enumerate(tar):
            if i >= ARCHIVE_ENTRIES_MAX:
                raise ValueError("TOO_MANY_ARCHIVE_ENTRIES")
            name = member.name
            if (not name or name.startswith("/") or "\\" in name
                    or any(p in ("", ".", "..") for p in name.rstrip("/").split("/"))):
                raise ValueError("UNSAFE_ARCHIVE_PATH")
            parts = PurePosixPath(name).parts
            if parts[0] not in ALLOWED_TREES or name.rstrip("/") in seen:
                raise ValueError("UNEXPECTED_OR_DUPLICATE_ARCHIVE_MEMBER")
            seen.add(name.rstrip("/"))
            if not (member.isfile() or member.isdir()):
                raise ValueError("ARCHIVE_SPECIAL_MEMBER")
            target = code.joinpath(*parts)
            for ancestor in (code, *[code.joinpath(*parts[:j]) for j in range(1, len(parts) + 1)]):
                if ancestor.is_symlink():
                    raise ValueError("STAGE_SYMLINK")
            if member.isdir():
                if not target.is_dir():
                    raise ValueError("STAGE_DIRECTORY_MISSING")
                continue
            total += member.size
            if member.size < 0 or member.size > MEMBER_MAX or total > ARCHIVE_MAX:
                raise ValueError("ARCHIVE_SIZE_LIMIT")
            expected_file = tar.extractfile(member)
            if expected_file is None:
                raise ValueError("ARCHIVE_FILE_MISSING")
            expected_bytes = expected_file.read(MEMBER_MAX + 1)
            actual_bytes = regular_bytes(str(target), MEMBER_MAX)
            if len(expected_bytes) != member.size or sha(expected_bytes) != sha(actual_bytes):
                raise ValueError("EXTRACTED_FILE_MISMATCH")
            files.add(name)
    for top in ALLOWED_TREES:
        base = code / top
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_symlink():
                raise ValueError("UNARCHIVED_SYMLINK")
            if path.is_file() and path.suffix in EXECUTABLE_EXTENSIONS and path.relative_to(code).as_posix() not in files:
                raise ValueError("UNARCHIVED_EXECUTABLE")
    return {"kind": "OFFICE_STAGE_OFFLINE", "status": "ARCHIVE_EXTRACT_MATCH",
            "package_sha256": pin, "verified_file_count": len(files),
            "mfa_verified": False, "passenger_verified": False, "safe_to_deploy": False}


def public_route_contract(evidence):
    """Assess previously collected evidence only; never issue HTTP requests."""
    if not isinstance(evidence, dict) or evidence.get("source") != "READ_ONLY_HTTP_OBSERVATION":
        raise ValueError("INVALID_OBSERVATION_FORMAT")
    routes = evidence.get("routes")
    if not isinstance(routes, dict):
        raise ValueError("MISSING_ROUTES")
    required = {"/": 200, "/api/health/": 200,
                "/company/office/messages/": 404, "/company/office/marketing/": 404}
    problems = []
    for route, expected in required.items():
        value = routes.get(route)
        if not isinstance(value, dict) or type(value.get("status")) is not int:
            problems.append({"route": route, "reason": "MISSING_STATUS"})
        elif value["status"] != expected:
            problems.append({"route": route, "reason": "STATUS_DIFFERENT_FROM_BLOCKED_BASELINE"})
    return {"kind": "PUBLIC_ROUTE_EVIDENCE_OFFLINE", "status": "BLOCKED_BASELINE_RECORDED" if not problems else "NEEDS_REVIEW",
            "problems": problems, "observation_timestamp": str(evidence.get("observed_at", "UNSPECIFIED"))[:40],
            "live_verification_performed_here": False, "release_permitted": False}


def game_source_gate(game, policy):
    """Conservative source-only G→S handoff, not a game build or browser test."""
    source = regular_bytes(game)
    flags = regular_bytes(policy)
    text = source.decode("utf-8")
    policy_text = flags.decode("utf-8")
    required = [r"function\s+nextMission\s*\(\)", r"function\s+resumeInMemoryCampaign\s*\(\)",
                r"canEnterGameplay\s*\("]
    missing = [name for name, pattern in zip(("nextMission", "resumeInMemoryCampaign", "canEnterGameplay"), required)
               if not re.search(pattern, text)]
    for flag in ("ownerApproved", "checkoutEnabled", "verifiedBackend"):
        if not re.search(r"\b" + flag + r"\s*:\s*false\b", policy_text):
            missing.append("MOJ1_OFF_" + flag)
    return {"kind": "GAME_SOURCE_OFFLINE", "status": "SOURCE_GUARDS_PRESENT" if not missing else "SOURCE_GUARD_MISSING",
            "missing": missing, "game_sha256": sha(source), "policy_sha256": sha(flags),
            "browser_verified": False, "full_build_verified": False, "safe_to_deploy": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("checkout")
    a.add_argument("--current", required=True); a.add_argument("--approved", required=True); a.add_argument("--sha256", required=True)
    b = sub.add_parser("office-stage")
    b.add_argument("--stage", required=True); b.add_argument("--sha256", required=True)
    c = sub.add_parser("public-routes")
    c.add_argument("--evidence", required=True)
    d = sub.add_parser("game-source")
    d.add_argument("--game", required=True); d.add_argument("--policy", required=True)
    args = p.parse_args()
    try:
        if args.command == "checkout": result = checkout(args.current, args.approved, args.sha256)
        elif args.command == "office-stage": result = office_stage(args.stage, args.sha256)
        elif args.command == "public-routes": result = public_route_contract(json.loads(regular_bytes(args.evidence)))
        else: result = game_source_gate(args.game, args.policy)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        accepted = ("PIN_MATCH", "FORMAT_ONLY_DRIFT", "ARCHIVE_EXTRACT_MATCH", "BLOCKED_BASELINE_RECORDED", "SOURCE_GUARDS_PRESENT")
        return 0 if result["status"] in accepted else 2
    except (OSError, ValueError, tarfile.TarError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": type(exc).__name__ if isinstance(exc, OSError) else str(exc),
                          "safe_to_deploy": False}, sort_keys=True)); return 2

if __name__ == "__main__":
    raise SystemExit(main())
