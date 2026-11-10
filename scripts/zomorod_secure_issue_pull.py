"""Pull encrypted owner commands from GitHub on cPanel without inbound SSH.

This is an intentionally fail-closed, one-command-per-run transport. It does
not interpret task contents, accept shell commands, or change the live server
until separately installed and configured by the owner. The existing private
``company_ingress.py`` decrypts and validates the encrypted task.

Examples (for an authorized administrator, after reviewing installation):

  python3 -B scripts/zomorod_secure_issue_pull.py --probe
  python3 -B scripts/zomorod_secure_issue_pull.py --bootstrap \
      --checkpoint /home/zomorod2/.private/zomorod-business/issue_pull.state
  python3 -B scripts/zomorod_secure_issue_pull.py --poll \
      --checkpoint /home/zomorod2/.private/zomorod-business/issue_pull.state \
      --db /path/to/existing/private.db \
      --hmac-key /path/to/existing/hmac.key \
      --recipient-key /path/to/existing/recipient.pem

Never put private credentials in GitHub, workflow inputs, or the command line.
The three credential arguments are *paths*, not secret values.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import ssl
import stat
import subprocess
import sys
import tempfile
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OWNER_LOGIN = "mojtabarozegar11-ship-it"
OWNER_USER_ID = 329077837
ISSUE = 1600
ENDPOINT = (
    "https://api.github.com/repos/mojtabarozegar11-ship-it/"
    "Saeit/issues/1600/comments"
)
MARKER = "ZMR-SEALED-COMMAND-V1\n"
ENVELOPE_KEYS = {"v", "alg", "ek", "iv", "ct", "mac"}
MAX_PAGES = 5
MAX_RESPONSE_BYTES = 2_000_000
MAX_ENVELOPE_BYTES = 24_000
DEFAULT_INGRESS = Path(
    "/home/zomorod2/.private/zomorod-business/company_ingress.py"
)


class PullError(RuntimeError):
    """Safe, non-sensitive diagnostic outcome."""


def _fetch_page(page: int) -> list[dict[str, Any]]:
    if not 1 <= page <= MAX_PAGES:
        raise PullError("PAGE_LIMIT")
    request = Request(
        f"{ENDPOINT}?per_page=100&page={page}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "ZomorodOwnerEncryptedPull/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=12, context=ssl.create_default_context()) as response:
            if response.status != 200:
                raise PullError("GITHUB_HTTP_NOT_OK")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise PullError("GITHUB_FETCH_UNAVAILABLE") from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise PullError("GITHUB_RESPONSE_TOO_LARGE")
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise PullError("GITHUB_INVALID_JSON") from exc
    if not isinstance(data, list) or len(data) > 100:
        raise PullError("GITHUB_INVALID_PAGE")
    return data


def fetch_comments() -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    seen: set[int] = set()
    for page in range(1, MAX_PAGES + 1):
        results = _fetch_page(page)
        for comment in results:
            if not isinstance(comment, dict) or type(comment.get("id")) is not int:
                raise PullError("GITHUB_INVALID_COMMENT")
            comment_id = comment["id"]
            if comment_id <= 0 or comment_id in seen:
                raise PullError("GITHUB_DUPLICATE_OR_INVALID_ID")
            seen.add(comment_id)
            comments.append(comment)
        if len(results) < 100:
            break
        if page == MAX_PAGES:
            raise PullError("GITHUB_PAGE_LIMIT_REACHED")
    return sorted(comments, key=lambda c: c["id"])


def eligible_envelope(comment: dict[str, Any]) -> str | None:
    user = comment.get("user")
    if (
        not isinstance(user, dict)
        or user.get("login") != OWNER_LOGIN
        or type(user.get("id")) is not int
        or user["id"] != OWNER_USER_ID
        or comment.get("author_association") != "OWNER"
        or comment.get("created_at") != comment.get("updated_at")
        or not isinstance(comment.get("created_at"), str)
    ):
        return None
    body = comment.get("body")
    if not isinstance(body, str) or not body.startswith(MARKER):
        return None
    raw = body[len(MARKER) :]
    if not 2 <= len(raw.encode("utf-8")) <= MAX_ENVELOPE_BYTES:
        return None
    try:
        envelope = json.loads(raw)
    except ValueError:
        return None
    if (
        not isinstance(envelope, dict)
        or set(envelope) != ENVELOPE_KEYS
        or envelope.get("v") != 1
        or envelope.get("alg") != "RSA-OAEP-256+A256CBC-HS256"
        or any(not isinstance(envelope[key], str) or not envelope[key]
               for key in ("ek", "iv", "ct", "mac"))
    ):
        return None
    # The private ingress is authoritative for cryptographic validation.
    return raw


def _private_regular_file(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    return (
        stat.S_ISREG(info.st_mode)
        and not info.st_mode & (stat.S_IRWXG | stat.S_IRWXO)
        and info.st_uid == os.geteuid()
    )


def _private_directory(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    return (
        stat.S_ISDIR(info.st_mode)
        and not info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        and info.st_uid == os.geteuid()
    )


@contextmanager
def checkpoint_lock(checkpoint: Path):
    if not _private_directory(checkpoint.parent):
        raise PullError("CHECKPOINT_DIRECTORY_INVALID")
    path = checkpoint.with_name(checkpoint.name + ".lock")
    flags = os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_mode & (stat.S_IRWXG | stat.S_IRWXO)
        ):
            raise PullError("CHECKPOINT_LOCK_UNSAFE")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PullError("ANOTHER_POLLER_RUNNING") from exc
        yield
    except OSError as exc:
        raise PullError("CHECKPOINT_LOCK_UNAVAILABLE") from exc
    finally:
        if "fd" in locals():
            os.close(fd)


def load_checkpoint(path: Path) -> dict[str, Any]:
    if not _private_regular_file(path):
        raise PullError("CHECKPOINT_NOT_PRIVATE_OR_MISSING")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PullError("CHECKPOINT_UNREADABLE") from exc
    if (
        not isinstance(state, dict)
        or set(state) != {"version", "last_id", "pending"}
        or state["version"] != 1
        or type(state["last_id"]) is not int
        or state["last_id"] < 0
        or (state["pending"] is not None and (
            not isinstance(state["pending"], dict)
            or set(state["pending"]) != {"id", "sha256"}
            or type(state["pending"]["id"]) is not int
            or state["pending"]["id"] <= state["last_id"]
            or not isinstance(state["pending"]["sha256"], str)
            or len(state["pending"]["sha256"]) != 64
        ))
    ):
        raise PullError("CHECKPOINT_INVALID")
    return state


def save_checkpoint(path: Path, state: dict[str, Any], *, create: bool = False) -> None:
    parent = path.parent
    if not _private_directory(parent):
        raise PullError("CHECKPOINT_DIRECTORY_INVALID")
    if path.is_symlink() or (path.exists() and not _private_regular_file(path)):
        raise PullError("CHECKPOINT_TARGET_UNSAFE")
    if create and path.exists():
        raise PullError("CHECKPOINT_ALREADY_INITIALIZED")
    fd, temp = tempfile.mkstemp(prefix=".issue_pull-", dir=parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, separators=(",", ":"), sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if create:
            try:
                os.link(temp, path)
            except FileExistsError as exc:
                raise PullError("CHECKPOINT_ALREADY_INITIALIZED") from exc
        else:
            os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def accept_envelope(
    raw: str, *, ingress: Path, db: Path, hmac_key: Path, recipient_key: Path
) -> None:
    if not ingress.is_file() or ingress.is_symlink():
        raise PullError("INGRESS_UNAVAILABLE")
    if not all(_private_regular_file(p) for p in (hmac_key, recipient_key)):
        raise PullError("PRIVATE_KEYS_UNAVAILABLE")
    if not db.is_file() or db.is_symlink():
        raise PullError("DATABASE_UNAVAILABLE")
    command = [
        sys.executable, "-B", str(ingress), "accept",
        "--db", str(db), "--hmac-key", str(hmac_key),
        "--recipient-key", str(recipient_key),
    ]
    try:
        result = subprocess.run(
            command, input=raw.encode("utf-8"), stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PullError("INGRESS_EXECUTION_UNAVAILABLE") from exc
    # The installed private ingress prints a multi-line receipt, not a bare
    # "ACCEPTED" token.  It also emits the *next* one-use public key after
    # rotating the recipient key.  Requiring the exact two success markers
    # prevents a successful DB import from being misclassified as a failure
    # (and leaving the write-ahead checkpoint permanently pending).
    output_lines = set(result.stdout.splitlines())
    if (
        result.returncode != 0
        or b"COMMAND_RECEIPT=ACCEPTED" not in output_lines
        or b"COMMAND_QUEUE=UPDATED" not in output_lines
    ):
        raise PullError("INGRESS_NOT_ACCEPTED")


def poll_once(
    checkpoint: Path, comments: list[dict[str, Any]],
    accept_callback,
) -> str:
    state = load_checkpoint(checkpoint)
    if state["pending"] is not None:
        raise PullError("PENDING_REQUIRES_MANUAL_RECONCILIATION")
    for comment in comments:
        comment_id = comment["id"]
        if comment_id <= state["last_id"]:
            continue
        raw = eligible_envelope(comment)
        if raw is None:
            state["last_id"] = comment_id
            save_checkpoint(checkpoint, state)
            continue
        # Write-ahead safety: if interrupted after the private import, a
        # second poll never blindly repeats that same command.
        state["pending"] = {
            "id": comment_id,
            "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        }
        save_checkpoint(checkpoint, state)
        accept_callback(raw)
        state["pending"] = None
        state["last_id"] = comment_id
        save_checkpoint(checkpoint, state)
        return "ONE_COMMAND_ACCEPTED"
    return "NO_NEW_AUTHORIZED_COMMAND"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--probe", action="store_true", help="Network only, no writes")
    mode.add_argument("--bootstrap", action="store_true", help="Skip existing comments")
    mode.add_argument("--poll", action="store_true", help="Accept at most one new task")
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--ingress", type=Path, default=DEFAULT_INGRESS)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--hmac-key", type=Path)
    parser.add_argument("--recipient-key", type=Path)
    args = parser.parse_args(argv)
    try:
        comments = fetch_comments()
        if args.probe:
            print("GITHUB_ISSUE_FETCH=OK")
            print(f"COMMENT_COUNT={len(comments)}")
            print("SERVER_MUTATION=NONE")
        elif args.bootstrap:
            if args.checkpoint is None:
                raise PullError("CHECKPOINT_REQUIRED")
            with checkpoint_lock(args.checkpoint):
                save_checkpoint(args.checkpoint, {
                    "version": 1,
                    "last_id": max((c["id"] for c in comments), default=0),
                    "pending": None,
                }, create=True)
            print("HISTORICAL_COMMANDS_SKIPPED=YES")
        else:
            if any(v is None for v in (
                args.checkpoint, args.db, args.hmac_key, args.recipient_key
            )):
                raise PullError("PRIVATE_PATH_ARGUMENTS_REQUIRED")
            with checkpoint_lock(args.checkpoint):
                outcome = poll_once(
                    args.checkpoint, comments,
                    lambda raw: accept_envelope(
                        raw, ingress=args.ingress, db=args.db,
                        hmac_key=args.hmac_key, recipient_key=args.recipient_key,
                    ),
                )
            print(f"ISSUE_PULL={outcome}")
        return 0
    except PullError as exc:
        print(f"ISSUE_PULL_BLOCKED={exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
