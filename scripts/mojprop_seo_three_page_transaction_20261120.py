"""Reviewed exact three-HTML publication transaction, no standalone CLI.

The caller MUST be an independently approved release controller satisfying
the existing full restore, tenant isolation, rollback and exact SHA gates.
This module never sets attestations, executes migrations, reloads services,
changes payment flags or edits configuration. Importing it has no side effects.
"""
from __future__ import annotations
import hashlib
import re

from scripts.mojprop_seo_current_live_v3_contract_20261120 import PINS, CHANGED, REQUIRED_ATTESTATIONS, build_v3

PROTECTED = {
    "signals/index.html": "05a80cd9dbec494a5e75a592ac7de79e54ee803fd3d234ab78fc6ab5cd73758d",
    "starter-30-trx/index.html": "bdf9a515dc59b6501c99480918f62fef4bab5b5f0d6d2231a6379b7077b6ab8d",
}
def digest(data):
    if type(data) is not bytes:
        raise ValueError("bytes required")
    return hashlib.sha256(data).hexdigest()

def require_release_gate(attestations, release_sha, owner_approved):
    # Missing, ambiguous or stale approvals fail closed. The caller is
    # responsible for obtaining these from the trusted release controller.
    if owner_approved is not True or not isinstance(release_sha,str) or not re.fullmatch(r"[0-9a-f]{40}",release_sha):
        raise PermissionError("explicit approved release SHA required")
    if any(attestations.get(k) != "true" for k in REQUIRED_ATTESTATIONS[:3]):
        raise PermissionError("independent restore/isolation/rollback evidence required")
    if attestations.get(REQUIRED_ATTESTATIONS[3]) != release_sha:
        raise PermissionError("approved release SHA mismatch")

def verify(read, expected):
    for path, sha in expected.items():
        if digest(read(path)) != sha:
            raise ValueError("release state differs from exact reviewed bytes: " + path)

def transaction(*, attestations, release_sha, owner_approved, historical,
                baseline, candidate, read_live, read_public, read_backup,
                replace_exact, exclusive_lock):
    """Perform only the verified three-file delta using a trusted host adapter.

    Adapter contract:
    - read functions use fixed tenant paths, reject symlinks/unsafe permissions;
      read_public verifies HTTPS 200, no redirect, bounded response.
    - read_backup serves independently restored, durable private exact originals.
    - exclusive_lock coordinates ALL writers to the affected pages.
    - replace_exact(path, expected_sha, bytes) uses an atomic no-follow
      replacement preserving ownership/mode; refuses unexpected source hashes.
    This core does not establish that a concrete adapter satisfies those rules.
    """
    require_release_gate(attestations,release_sha,owner_approved)
    expected,_ = build_v3(historical,baseline)
    if set(candidate)!=set(expected) or any(candidate[p]!=expected[p] for p in expected):
        raise ValueError("unreviewed candidate")
    before={p:pair[0] for p,pair in PINS.items()} | PROTECTED
    after={p:pair[1] for p,pair in PINS.items()} | PROTECTED
    with exclusive_lock():
        verify(read_live,before)
        verify(read_public,before)
        verify(read_backup,{p:PINS[p][0] for p in CHANGED})
        attempted=[]
        try:
            for path in CHANGED:
                attempted.append(path)
                replace_exact(path,PINS[path][0],candidate[path])
            verify(read_live,after)
            verify(read_public,after)
        except BaseException as original:
            unresolved=[]
            for path in reversed(attempted):
                try:
                    current=digest(read_live(path))
                    if current==PINS[path][1]:
                        replace_exact(path,current,baseline[path])
                    elif current!=PINS[path][0]:
                        unresolved.append(path)
                except BaseException:
                    unresolved.append(path)
            try:
                verify(read_live,before)
                verify(read_public,before)
            except BaseException:
                unresolved.append("post_rollback_verification")
            if unresolved:
                raise RuntimeError("ROLLBACK_UNVERIFIED:" + ",".join(unresolved)) from original
            raise RuntimeError("RELEASE_ABORTED_EXACT_ROLLBACK_VERIFIED") from original
    return {"released_paths":list(CHANGED),"public_verified":True,
            "release_sha":release_sha,"database_modified":False}
