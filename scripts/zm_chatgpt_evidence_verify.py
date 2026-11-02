#!/usr/bin/env python3
"""Bounded, read-only GitHub evidence checks for Zomorod cycle 05.

An existing GitHub object or green CI job is *not* proof of a live deployment,
bank settlement, customer delivery, employment or business impact.  This
worker produces a separate private attestation; it never modifies the ledger,
the immutable report archive, or the action index.
"""

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from zm_chatgpt_action_index import INDEX_NAME, SOURCE, guard_private


ATTESTATION_NAME = "chatgpt_evidence_attestations.json"
API = "https://api.github.com/repos/mojtabarozegar11-ship-it/Saeit"
PATTERN = re.compile(
    r"https://github\.com/mojtabarozegar11-ship-it/Saeit/"
    r"(?:(commit)/([a-f0-9]{40})|(actions/runs)/([1-9][0-9]*)|"
    r"(pull)/([1-9][0-9]*)|(issues)/([1-9][0-9]*)(?:#issuecomment-[1-9][0-9]*)?)\Z"
)


def github_json(path, *, token="", opener=urlopen):
    """Only paths derived from the strict GitHub URL matcher reach this call."""
    if not re.fullmatch(r"/(?:commits/[a-f0-9]{40}|actions/runs/[1-9][0-9]*|"
                        r"pulls/[1-9][0-9]*|issues/[1-9][0-9]*)", path):
        raise ValueError("UNSAFE_GITHUB_API_PATH")
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "ZM-Action-Evidence-Audit/1.0",
               "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request(API + path, headers=headers)
    try:
        with opener(req, timeout=8) as response:
            data = response.read(1_000_001)
    except (HTTPError, URLError, TimeoutError, OSError):
        return None
    if len(data) > 1_000_000:
        return None
    try:
        result = json.loads(data)
    except (UnicodeDecodeError, ValueError):
        return None
    return result if isinstance(result, dict) else None


def classify_url(url, *, fetch=github_json):
    """Validate evidence reference only, never infer completed business action."""
    match = PATTERN.fullmatch(url)
    if not match:
        return "invalid_reference"
    kind = next(match.group(i) for i in (1, 3, 5, 7) if match.group(i))
    identifier = next(match.group(i) for i in (2, 4, 6, 8) if match.group(i))
    suffix = {"commit": "commits", "actions/runs": "actions/runs",
              "pull": "pulls", "issues": "issues"}[kind]
    result = fetch("/" + suffix + "/" + identifier)
    if result is None:
        return "unavailable"
    if kind == "commit":
        return "source_exists" if result.get("sha") == identifier else "mismatch"
    if kind == "actions/runs":
        repo = result.get("repository")
        if not isinstance(repo, dict) or repo.get("full_name") != "mojtabarozegar11-ship-it/Saeit" or str(result.get("id")) != identifier:
            return "mismatch"
        if result.get("status") == "completed" and result.get("conclusion") == "success":
            return "ci_success"
        return "ci_not_successful"
    if kind == "pull":
        if str(result.get("number")) != identifier:
            return "mismatch"
        return "merged_source" if result.get("merged_at") and result.get("merged") is True else "proposal_only"
    return "issue_exists" if str(result.get("number")) == identifier else "mismatch"


def read_actions(path):
    guard_private(path, INDEX_NAME, must_exist=True)
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5) as db:
        db.execute("PRAGMA query_only=ON")
        if (db.execute("PRAGMA user_version").fetchone() != (1,) or
                db.execute("SELECT value FROM metadata WHERE name='source'").fetchone() != (SOURCE,) or
                db.execute("SELECT value FROM metadata WHERE name='verification'").fetchone() != ("not_checked",) or
                db.execute("PRAGMA integrity_check").fetchone() != ("ok",)):
            raise ValueError("ACTION_INDEX_IDENTITY_OR_INTEGRITY")
        return db.execute("SELECT action_id,receipt_sha256,evidence_url,action_status "
                          "FROM actions ORDER BY seq").fetchall()


def evaluate(rows, *, fetch=github_json, limit=30):
    if not 1 <= limit <= 100:
        raise ValueError("EVIDENCE_LIMIT_INVALID")
    candidates = [i for i, row in enumerate(rows) if row[3] == "completed" and row[2]]
    selected = set(candidates[-limit:])
    results, examined = [], 0
    for i, (action_id, digest, url, action_status) in enumerate(rows):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{7,79}", action_id) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("ACTION_RECEIPT_INVALID")
        status = "not_checked"
        if i in selected:
            status = classify_url(url, fetch=fetch)
            examined += 1
        results.append({"action_id": action_id, "receipt_sha256": digest,
                        "reference_status": status})
    return results, examined


def write_attestation(output, payload):
    guard_private(output, ATTESTATION_NAME)
    lock = output.parent / ".chatgpt-evidence.lock"
    if lock.is_symlink():
        raise ValueError("UNSAFE_EVIDENCE_LOCK")
    lock_fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        if os.fstat(lock_fd).st_mode & 0o077:
            raise ValueError("UNSAFE_EVIDENCE_LOCK_MODE")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        guard_private(output, ATTESTATION_NAME)
        if output.exists():
            old = json.loads(output.read_text(encoding="utf-8"))
            if old.get("schema_version") != 1 or old.get("source") != SOURCE:
                raise ValueError("OLD_ATTESTATION_IDENTITY")
            old_ids = {r["action_id"]: r["receipt_sha256"] for r in old.get("results", [])}
            new_ids = {r["action_id"]: r["receipt_sha256"] for r in payload["results"]}
            if any(new_ids.get(k) != v for k, v in old_ids.items()):
                raise ValueError("IMMUTABLE_ATTESTATION_HISTORY_CHANGED")
        fd, name = tempfile.mkstemp(prefix=".zm-evidence-", dir=output.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, output)
        finally:
            Path(name).unlink(missing_ok=True)
    finally:
        os.close(lock_fd)


def run(index, output, *, limit=30, commit=False, fetch=github_json):
    if index.parent != output.parent or index == output:
        raise ValueError("EVIDENCE_PRIVATE_DIRECTORY_MISMATCH")
    guard_private(output, ATTESTATION_NAME)
    rows = read_actions(index)
    results, examined = evaluate(rows, fetch=fetch, limit=limit)
    digest = hashlib.sha256()
    with index.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    payload = {"schema_version": 1, "source": SOURCE,
               "index_sha256": digest.hexdigest(),
               "checked_at": datetime.now(timezone.utc).isoformat(),
               "business_effect_verified": False, "results": results}
    if commit:
        if os.getenv("ZM_ACTION_EVIDENCE_VERIFY_ENABLED") != "1":
            raise ValueError("EVIDENCE_COMMIT_GATE_DISABLED")
        write_attestation(output, payload)
    return {"indexed": len(rows), "references_checked": examined,
            "github_ci_success_refs": sum(r["reference_status"] == "ci_success" for r in results),
            "business_effect_verified": 0,
            "mode": "commit" if commit else "preview"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    token = os.environ.get("ZM_GITHUB_REPORTS_READ_TOKEN", "")
    print(json.dumps(run(args.index, args.output, limit=args.limit,
                         commit=args.commit,
                         fetch=lambda path: github_json(path, token=token)),
                     sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
