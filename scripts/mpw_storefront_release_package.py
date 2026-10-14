"""Build a private, reviewable MojPlayWin *candidate* release, never deploy it.

Input must be the exact currently installed cPanel brand view, copied into an
authorized private working directory. This generator NEVER writes to the
active site, never alters products or databases, and never uses SSH.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
from tempfile import TemporaryDirectory

try:
    from scripts.mpw_branded_store_targeted_patch import prepare
except ModuleNotFoundError:
    from mpw_branded_store_targeted_patch import prepare

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "core/factory_storefront.py",
    "core/brand_store_integration.py",
    "core/templates/core/includes/mpw_verified_factory_cards.html",
)
LIVE_BRAND = "core/brand_views.py"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_package(active_source: Path, destination: Path):
    """Create an inert release candidate containing everything needed for review.

    Existing destination is refused to avoid overwriting another session. The
    output contains the exact original view to restore and a patched candidate.
    No file inside the active Django installation is opened for writing.
    """
    if active_source.is_symlink() or not active_source.is_file():
        raise ValueError("BASELINE_MISSING_OR_SYMLINK")
    active = active_source.resolve(strict=True)
    if not active.name == "brand_views.py":
        raise ValueError("UNEXPECTED_LIVE_SOURCE_NAME")
    dst_parent = destination.parent.resolve(strict=True)
    dst = dst_parent / destination.name
    if dst.exists() or dst.is_symlink():
        raise ValueError("RELEASE_OUTPUT_ALREADY_EXISTS")
    site_root = active.parent.parent
    if dst == active or dst == site_root or site_root in dst.parents:
        raise ValueError("UNSAFE_OUTPUT_LOCATION")
    preimage = active.read_bytes()
    candidate, count = prepare(preimage.decode("utf-8"))
    if count != 1:
        raise RuntimeError("UNEXPECTED_EDIT_SCOPE")
    candidate_bytes = candidate.encode("utf-8")
    if sha256(candidate_bytes) == sha256(preimage):
        raise RuntimeError("NO_PATCH_EFFECT")
    for rel in FILES:
        file = ROOT / rel
        if file.is_symlink() or not file.is_file():
            raise ValueError("REQUIRED_RELEASE_COMPONENT_MISSING")
        if file.suffix == ".py":
            compile(file.read_text("utf8"), rel, "exec")
    with TemporaryDirectory(prefix=".mpw-candidate-", dir=dst_parent) as tmp:
        work = Path(tmp)
        os.chmod(work, 0o700)
        originals = work/"rollback"
        originals.mkdir(mode=0o700)
        (originals / "brand_views.py").write_bytes(preimage)
        target = work / LIVE_BRAND
        target.parent.mkdir(parents=True)
        target.write_bytes(candidate_bytes)
        for rel in FILES:
            dest = work / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes((ROOT / rel).read_bytes())
        manifest = {
            "format": "mojplaywin-safe-brand-release-candidate-v1",
            "candidate_only_not_deployed": True,
            "product_activation_performed": False,
            "paid_checkout_enabled": False,
            "live_destination": LIVE_BRAND,
            "baseline_sha256": sha256(preimage),
            "candidate_sha256": sha256(candidate_bytes),
            "rollback_path_in_package": "rollback/brand_views.py",
            "scope": "single branded_store function; three new related helper/template files",
            "payload_sha256": {
                rel: sha256((work / rel).read_bytes()) for rel in (LIVE_BRAND,) + FILES
            },
            "preflight_required": [
                "authorized on-host access",
                "fresh recoverable backups",
                "verify current live source SHA matches baseline_sha256",
                "candidate import and Django template smoke in private shadow",
                "controlled atomic file promotion with rollback",
                "actual MojPlayWin store HTTP smoke",
                "separate owner-approved free product activation",
            ],
        }
        manifest_file = work / "manifest.json"
        manifest_file.write_text(json.dumps(manifest, indent=2, sort_keys=True)+"\n")
        for p in work.rglob("*"):
            if p.is_file():
                p.chmod(0o600)
        # Copy to a brand-new directory only. This is a review artifact,
        # never the live site's code tree.
        shutil.copytree(work,dst,symlinks=False)
    if sha256((dst/"rollback/brand_views.py").read_bytes()) != manifest["baseline_sha256"]:
        raise RuntimeError("ROLLBACK_PREIMAGE_INVALID")
    for rel,digest in manifest["payload_sha256"].items():
        if sha256((dst/rel).read_bytes()) != digest:
            raise RuntimeError("CANDIDATE_BUNDLE_DIGEST_INVALID")
    return manifest


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--active-source",type=Path,required=True)
    p.add_argument("--output-directory",type=Path,required=True)
    args=p.parse_args()
    result=build_package(args.active_source,args.output_directory)
    print(json.dumps(result,sort_keys=True))


if __name__=="__main__":
    main()
