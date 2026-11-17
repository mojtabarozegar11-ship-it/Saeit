#!/usr/bin/env python3
"""C133: side-effect-free inspection of three Moj Prop release branch merges.

Reads local Git history and simulates merge in Git's *ephemeral runner object
database*, not the repository's remote. Never checkout, reset, merge, push,
delete, connect to production, access buyer PII, send mail, or call billing.
A PR's mergeable flag without concrete conflict paths is not a release plan.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import subprocess
import sys

REFS = {
    "main": "refs/remotes/origin/main",
    "prop_canonical": "refs/remotes/origin/feature/prop-firm-policy-v11-20261114",
    "public_static": "refs/remotes/origin/fix/mojprop-main-prelaunch-real-plan1-20261116",
}
PAIRS = (
    ("main", "prop_canonical"),
    ("main", "public_static"),
    ("prop_canonical", "public_static"),
)
OID = re.compile(r"[a-f0-9]{40}|[a-f0-9]{64}\Z")
MAX_PATHS = 4096
MAX_BYTES = 512 * 1024

@dataclass(frozen=True)
class MergeObservation:
    base: str
    head: str
    base_sha: str
    head_sha: str
    result: str
    conflicting_paths: tuple[str, ...]
    digest: str = ""

    @property
    def count(self) -> int:
        return len(self.conflicting_paths)


def _git(root: Path, args: list[str], *, timeout: int = 90):
    return subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True, errors="replace",
                          timeout=timeout, check=False)


def _sha(root: Path, ref: str) -> str:
    result = _git(root, ["rev-parse", "--verify", ref + "^{commit}"], timeout=12)
    value = result.stdout.strip()
    if result.returncode != 0 or not OID.fullmatch(value):
        raise RuntimeError("required exact reviewed branch unavailable")
    return value


def _valid_path(value: str) -> bool:
    return (type(value) is str and 1 <= len(value) <= 500
            and not value.startswith(("/", "../", "./"))
            and "\x00" not in value and "\r" not in value
            and "\n" not in value
            and all(ord(c) >= 32 and ord(c) != 127 for c in value)
            and not any(part in ("..", ".") for part in value.split("/")))


def inspect(root: Path, base: str, head: str) -> MergeObservation:
    if base not in REFS or head not in REFS or base == head:
        raise ValueError("unsupported pinned comparison")
    left = _sha(root, REFS[base])
    right = _sha(root, REFS[head])
    if left == right:
        return MergeObservation(base, head, left, right, "clean", ())
    output = _git(root, [
        "merge-tree", "--write-tree", "--name-only", "--no-messages", left, right,
    ], timeout=90)
    # exit 0: clean merge; exit 1: conflicts. Any other exit is UNKNOWN.
    if output.returncode not in (0, 1) or len(output.stdout) > MAX_BYTES:
        raise RuntimeError("merge-tree diagnostic incomplete")
    rows = output.stdout.splitlines()
    if not rows or not OID.fullmatch(rows[0]):
        raise RuntimeError("unexpected git merge-tree output")
    if output.returncode == 0:
        if len(rows) != 1:
            raise RuntimeError("unexpected clean merge data")
        return MergeObservation(base, head, left, right, "clean", ())
    conflicting = tuple(sorted(set(rows[1:])))
    if (not conflicting or len(conflicting) > MAX_PATHS
            or any(not _valid_path(item) for item in conflicting)):
        raise RuntimeError("invalid or truncated conflict path inventory")
    digest = hashlib.sha256(
        "\n".join(conflicting).encode("utf-8", "strict")
    ).hexdigest()
    return MergeObservation(base, head, left, right,
                            "blocked_by_conflicts", conflicting, digest)


def _risk(path: str) -> str:
    if path.startswith(("prop_firm/migrations/", "core/consent_", "core/moj_prop_")):
        return "crm_model_consent"
    if path in ("config/urls.py", "config/settings.py") or path.startswith("prop_firm/"):
        return "django_runtime"
    if path.startswith(".github/workflows/"):
        return "ci_deploy_controls"
    if path.startswith(("templates/moj-prop", "core/templates/mojplaywin/moj_prop")):
        return "public_buyer_ui"
    if any(s in path for s in ("payment", "wallet", "invoice", "checkout")):
        return "payment_boundary"
    return "other"


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        raise SystemExit("usage: python scripts/mojprop_merge_conflict_readonly_c133.py")
    root = Path.cwd()
    try:
        checked = [_sha(root, REFS[name]) for name in REFS]
        observations = [inspect(root, *pair) for pair in PAIRS]
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        # Never hide an unavailable ref behind a green 'zero conflicts'.
        print("MOJPROP_C133_CONFLICT_AUDIT=UNKNOWN")
        print("MOJPROP_C133_RELEASE_AUTHORIZED=false")
        return 2
    print("MOJPROP_C133_BASE_MAIN_SHA=" + checked[0])
    print("MOJPROP_C133_CANONICAL_SHA=" + checked[1])
    print("MOJPROP_C133_STATIC_SHA=" + checked[2])
    print("MOJPROP_C133_SOURCE_READONLY=true")
    print("MOJPROP_C133_LIVE_RELEASE_AUTHORIZED=false")
    print("MOJPROP_C133_PAYMENT_OR_CUSTOMER_POST=false")
    for observation in observations:
        prefix = "MOJPROP_C133_" + observation.base.upper() + "_VS_" + observation.head.upper()
        print(prefix + "_STATE=" + observation.result)
        print(prefix + "_CONFLICT_COUNT=" + str(observation.count))
        if observation.digest:
            print(prefix + "_PATHSET_SHA256=" + observation.digest)
        if observation.conflicting_paths:
            counts = {}
            for p in observation.conflicting_paths:
                name = _risk(p)
                counts[name] = counts.get(name, 0) + 1
            for kind, count in sorted(counts.items()):
                print(prefix + "_RISK_" + kind.upper() + "=" + str(count))
            for path in observation.conflicting_paths[:60]:
                print(prefix + "_CONFLICT_PATH=" + path)
            if observation.count > 60:
                print(prefix + "_ADDITIONAL_CONFLICTS_HIDDEN=" + str(observation.count - 60))
    # A *successful diagnostic* is never approval to merge or deploy.
    print("MOJPROP_C133_CONFLICT_AUDIT=COMPLETE_READONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
