#!/usr/bin/env python3
"""R-01 isolated source-only verifier candidate (C116), not F-owned release.\n\nFixes root-symlink normalization bypass in C112; no factory, chain, or signing writes.\nNot hardened against hostile concurrent filesystem mutation (TOCTOU).\nRead-only, fail-closed MOJ1 V2 independent-auditor input verifier.

Usage: python moj1_c112_frozen_auditor_input_verify.py --root FROZEN_CHECKOUT --manifest PRIVATE_MANIFEST.json
No network, chain calls, signing, keys, payment, compilation, or contract deployment.
Manifest example (private): {"frozen_commit":"4411b28325be44c54d7917b4c67786348521b6a9",
 "compiler":"0.8.25","files":[{"path":"experiments/moj1-pilot/contracts/MojCoinGuarded.sol","sha256":"64hex"},...],
 "dependency_files":[{"path":"node_modules/@openzeppelin/tron-contracts/...","sha256":"64hex"},...],
 "build_files":[{"path":"experiments/moj1-pilot/package-lock.json","sha256":"64hex"},...]}
The placeholder '64hex' is NOT a valid digest; an auditor must independently compute real SHA-256s.
"""
import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys

FROZEN = "4411b28325be44c54d7917b4c67786348521b6a9"
BASE = "experiments/moj1-pilot/contracts/"
CONTRACTS = {BASE + name for name in (
    "MojCoinGuarded.sol", "MojGenesisFactoryGuarded.sol",
    "MojVestingVault.sol", "MojApprovalReserve.sol"
)}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
def fail(message):
    raise ValueError(message)

def checked_file(root, entry):
    if not isinstance(entry, dict):
        fail("manifest entry must be an object")
    rel = entry.get("path")
    digest = entry.get("sha256")
    if not isinstance(rel, str) or not rel or "\\" in rel or rel.startswith("/"):
        fail("invalid relative path")
    pure = pathlib.PurePosixPath(rel)
    if any(p in (".", "..") for p in rel.split("/")) or str(pure) != rel:
        fail("noncanonical relative path: " + rel)
    if not isinstance(digest, str) or not HEX64.fullmatch(digest):
        fail("missing real lowercase SHA-256 for " + rel)
    target = root
    for part in pure.parts:
        target = target / part
        if target.is_symlink():
            fail("symlink in path: " + rel)
    if not target.is_file():
        fail("missing regular file: " + rel)
    actual = hashlib.sha256(target.read_bytes()).hexdigest()
    if actual != digest:
        fail("digest mismatch: " + rel)
    return rel

def verify(root, manifest):
    if not root.is_dir() or root.is_symlink():
        fail("root must be a real directory")
    if manifest.get("frozen_commit") != FROZEN:
        fail("wrong frozen source commit")
    if manifest.get("compiler") != "0.8.25":
        fail("compiler version is not the declared 0.8.25; toolchain settings require separate audit")
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=False, timeout=10)
    if result.returncode != 0 or result.stdout.strip() != FROZEN:
        fail("checkout HEAD does not match frozen commit")
    files = manifest.get("files")
    dependencies = manifest.get("dependency_files")
    builds = manifest.get("build_files")
    if not all(isinstance(v, list) and v for v in (files, dependencies, builds)):
        fail("contract, dependency, and build-file hash lists must all be nonempty")
    contract_names = {e.get("path") for e in files if isinstance(e, dict)}
    if contract_names != CONTRACTS or len(files) != len(CONTRACTS):
        fail("manifest must contain exactly the four scoped guarded contracts")
    all_entries = files + dependencies + builds
    names = [checked_file(root, e) for e in all_entries]
    if len(set(names)) != len(names):
        fail("duplicate manifest path")
    if not any("lock" in name.lower() for name in (e["path"] for e in builds)):
        fail("missing locked dependency manifest")
    if not any("@openzeppelin/tron-contracts/" in name for name in (e["path"] for e in dependencies)):
        fail("transitive OpenZeppelin TRON dependency bytes not enumerated")
    return len(all_entries)

def checked_root_path(path):
    """Fail closed on a symlink at root or any existing ancestor; do not resolve first."""
    absolute = path.absolute()  # pathlib.absolute does NOT dereference symlinks
    for component in (absolute, *absolute.parents):
        if component.is_symlink():
            fail("symlinked checkout root or ancestor: " + str(component))
    return absolute

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=pathlib.Path)
    parser.add_argument("--manifest", required=True, type=pathlib.Path)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            fail("manifest must be a JSON object")
        n = verify(checked_root_path(args.root), manifest)
    except (ValueError, OSError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print("NO_GO: " + str(exc), file=sys.stderr)
        return 2
    print(f"INPUT_HASHES_VERIFIED: {n} files; NOT a security audit, deployment approval or contract certification")
    return 0

if __name__ == "__main__":
    sys.exit(main())
