#!/usr/bin/env python3
"""RFQ_INTAKE-only verified atomic update of official Zomorod RFQs 350-421.

No order/payment/contract/DB state. No rewrite, legacy notice, original kit,
robots policy, or other routes are edited. Runs only via pinned cPanel SSH and
a known private stage SHA. Existing live bytes must match the immutable
pre-RFQ_INTAKE Git blob SHAs recorded at source.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

HOME = Path.home()
ROOT = Path("/home/zomorod2/public_html")
SERIALS = tuple(range(350, 422))
LOCK = HOME / ".locks/zomorod-auctions-rfq-intake.lock"
MARKER = "zm-rfq-intake-20261117-"


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def regular(path):
    return path.is_file() and not path.is_symlink()


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha(path):
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def stage_dir(commit):
    require(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "Invalid SHA")
    return HOME / (".zm-auctions-rfq-intake-stage-" + commit)


def backup_dir(commit):
    return HOME / ".backups/zomorod-auctions-rfq-intake" / commit


def source_path(stage, rel):
    return stage / rel


def target_path(rel):
    m = re.fullmatch(r"public/auctions/(\d{3})/index.html", rel)
    if m:
        n = int(m.group(1))
        require(n in SERIALS, "Number out of target range")
        return ROOT / ("zm-auction" + str(n)) / "index.html"
    raise RuntimeError("Refuse to publish unrelated source: " + rel)


def verified_domain_root():
    require(HOME.as_posix() == "/home/zomorod2" and os.geteuid() != 0,
            "Unexpected user")
    require(ROOT.is_dir() and not ROOT.is_symlink()
            and ROOT.resolve() == ROOT and ROOT.stat().st_uid == os.geteuid(),
            "Unverified cPanel root")
    try:
        raw = subprocess.check_output(
            ["uapi", "--output=json", "DomainInfo", "domains_data"],
            stderr=subprocess.PIPE, timeout=30)
        info = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired) as exc:
        raise RuntimeError("cPanel DomainInfo unavailable") from exc
    matches = []
    def scan(obj):
        if isinstance(obj, dict):
            d = obj.get("domain") or obj.get("servername")
            p = obj.get("documentroot") or obj.get("document_root") or obj.get("docroot")
            if d == "zomorodmelal.ir":
                matches.append(p)
            for x in obj.values():
                scan(x)
        elif isinstance(obj, list):
            for x in obj:
                scan(x)
    scan(info)
    require(matches == [str(ROOT)], "DomainInfo changed or ambiguous")
    ht = ROOT / ".htaccess"
    require(regular(ht), "Apache routing missing")
    data = ht.read_bytes()
    require(b"# zm-auctions-official-350-421-v1" in data, "Published 350-421 route not verified")
    require(b"RewriteRule ^auctions/(35[0-9]|3[6-9][0-9]|4[01][0-9]|42[01])/?$ /zm-auction$1/index.html [END,NC]" in data,
            "Expected exact scoped numbering rewrite absent")
    for n in range(346, 350):
        token = ("RewriteRule ^auctions/" + str(n) + "/?$ /zm-auction"
                 + str(n) + "/index.html [END,NC]").encode()
        require(data.count(token) == 1 and regular(ROOT / ("zm-auction" + str(n)) / "index.html"),
                "Original RFQ missing: " + str(n))
    require(b"RewriteRule ^auctions/?$ /zm-auctions-index/index.html [END,NC]" in data,
            "Original index rewrite changed")
    require(b"RewriteRule ^sitemap-auctions[.]xml$ /zm-auctions-index/sitemap.xml [END,NC]" in data,
            "Original sitemap rewrite changed")
    for rel in ("index.html", "zm-auctions-index/supplier-kit/index.html",
                "zm-auctions-index/index.html", "zm-auctions-index/sitemap.xml"):
        require(regular(ROOT / rel), "Essential original route missing: " + rel)
    return ht


def protected():
    paths = [ROOT / ".htaccess", ROOT / "index.html",
             ROOT / "zm-auctions-index/supplier-kit/index.html",
             ROOT / "zm-auctions-index/index.html",
             ROOT / "zm-auctions-index/sitemap.xml"]
    paths += [ROOT / ("zm-auction" + str(n)) / "index.html" for n in range(346, 350)]
    if regular(ROOT / "robots.txt"):
        paths.append(ROOT / "robots.txt")
    return {str(p): sha256(p) for p in paths}


def staged_plan(stage):
    require(stage.is_dir() and not stage.is_symlink(), "Invalid private stage")
    path = stage / "content/auctions-rfq-intake-20261117/baseline.json"
    require(regular(path), "Missing approved baseline manifest")
    plan = json.loads(path.read_text(encoding="utf-8"))
    baseline = plan["baseline_git_blob_sha1"]
    expected = {f"public/auctions/{n}/index.html" for n in SERIALS}
    require(set(baseline) == expected, "Unexpected manifest asset set")
    require(plan["source_main_commit"] == "1b38c32003c8c1a39cb0c9308d29e9ade83d501d", "Unverified source baseline")
    assets = []
    for rel in sorted(expected):
        source = source_path(stage, rel)
        target = target_path(rel)
        require(regular(source), "Staged source missing: " + rel)
        require(target.parent.is_dir() and not target.parent.is_symlink()
                and regular(target), "Unrecognized production target: " + str(target))
        data = source.read_text(encoding="utf-8")
        if re.fullmatch(r"public/auctions/\d{3}/index.html", rel):
            n = int(rel.split("/")[2])
            require(f"{MARKER}{n}" in data and f"zm-auctions-72-v1 official-{n}" in data,
                    "RFQ intake marker or original serial missing: " + str(n))
            require(f'id="rfq-offer-form-{n}"' in data and f"var n={n}," in data,
                    "Missing matching number in local-only form script: " + str(n))
            require(f"https://zomorodmelal.ir/auctions/{n}/" in data
                    and "zomorodmelal@gmail.com" in data, "Bad RFQ_INTAKE canonical/contact")
        assets.append((rel, source, target, baseline[rel]))
    require(len(assets) == 72, "Expected exactly 72 physical files")
    return assets


def atomic_write(target, content):
    require(regular(target), "Refusing absent or symlink target")
    prior_mode = stat.S_IMODE(target.stat().st_mode)
    tmp = target.with_name("." + target.name + ".zm-rfq-intake-20261117-tmp")
    require(not tmp.exists() and not tmp.is_symlink(), "Old RFQ_INTAKE temp exists")
    try:
        with tmp.open("xb") as fd:
            fd.write(content)
            fd.flush()
            os.fsync(fd.fileno())
        tmp.chmod(prior_mode)
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()


def manifest_file(commit):
    return backup_dir(commit) / "release.json"


def preflight(stage):
    verified_domain_root()
    assets = staged_plan(stage)
    for rel, source, target, old_git_sha in assets:
        require(git_blob_sha(target) == old_git_sha,
                "Live file differs from reviewed RFQ_INTAKE baseline: " + rel)
    print("AUCTIONS_RFQ_INTAKE_PREFLIGHT=72_reviewed_sha1_blobs_matched", flush=True)
    return assets


def rollback(commit, stage):
    record = manifest_file(commit)
    require(regular(record), "Release manifest missing; refusing blind rollback")
    info = json.loads(record.read_text(encoding="utf-8"))
    assets = staged_plan(stage)
    saved = backup_dir(commit)
    for rel, source, target, _old in assets:
        original = saved / rel
        require(regular(original) and regular(target), "Backup or target absent: " + rel)
        present = sha256(target)
        require(present in (sha256(original), sha256(source)),
                "Concurrent edit blocks rollback: " + rel)
    for rel, source, target, _old in assets:
        original = saved / rel
        if sha256(target) == sha256(source):
            atomic_write(target, original.read_bytes())
    for path, hash_before in info["protected"].items():
        require(regular(Path(path)) and sha256(Path(path)) == hash_before,
                "Protected original changed: " + path)
    info["status"] = "rolled_back"
    atomic_write(record, (json.dumps(info,ensure_ascii=False,indent=2)+"\n").encode())
    print("AUCTIONS_RFQ_INTAKE_ROLLBACK=72_original_files_restored",flush=True)


def verify(commit, stage):
    verified_domain_root()
    assets = staged_plan(stage)
    record = manifest_file(commit)
    require(regular(record), "Missing release audit manifest")
    info = json.loads(record.read_text(encoding="utf-8"))
    for rel, source, target, _ in assets:
        require(sha256(source) == sha256(target), "RFQ_INTAKE source/live mismatch " + rel)
    for path, h in info["protected"].items():
        require(regular(Path(path)) and sha256(Path(path)) == h,
                "Existing official file changed: " + path)
    print("AUCTIONS_RFQ_INTAKE_CPANEL=72_exact_source_hashes_verified",flush=True)
    print("AUCTIONS_RFQ_INTAKE_LEGACY=346_349_and_supplier_kit_unchanged",flush=True)


def apply(commit, stage):
    assets = preflight(stage)
    bdir = backup_dir(commit)
    require(not bdir.exists() and not bdir.is_symlink(), "RFQ_INTAKE backup already exists")
    total = sum(source.stat().st_size + target.stat().st_size for _,source,target,_ in assets)
    require(shutil.disk_usage(ROOT).free > 4 * total + 2_000_000,
            "Insufficient quota for private backups and atomic updates")
    bdir.mkdir(parents=True, mode=0o700)
    for rel, _, target, _ in assets:
        saved = bdir / rel
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(target, saved)
        require(sha256(saved) == sha256(target), "Backup validation failure: " + rel)
    info = {"sha":commit,"status":"applying","protected":protected(),"target_count":72}
    record = manifest_file(commit)
    record.write_text(json.dumps(info,ensure_ascii=False,indent=2)+"\n", encoding="utf-8")
    try:
        # Details first, public collection and sitemap last. Never touch .htaccess.
        for rel, source, target, _ in assets:
            atomic_write(target, source.read_bytes())
        verify(commit, stage)
        info["status"] = "deployed"
        atomic_write(record,(json.dumps(info,ensure_ascii=False,indent=2)+"\n").encode())
        print("AUCTIONS_RFQ_INTAKE_RELEASE=72_structured_proposal_forms_published",flush=True)
    except Exception:
        rollback(commit, stage)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation",choices=("check","apply","verify","rollback"))
    parser.add_argument("commit")
    args = parser.parse_args()
    stage = stage_dir(args.commit)
    require(stage.is_dir() and not stage.is_symlink(), "Private RFQ_INTAKE stage absent")
    LOCK.parent.mkdir(parents=True,exist_ok=True)
    with LOCK.open("a+") as fd:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.operation == "check":
            preflight(stage)
        elif args.operation == "apply":
            apply(args.commit, stage)
        elif args.operation == "verify":
            verify(args.commit, stage)
        else:
            rollback(args.commit, stage)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("AUCTIONS_RFQ_INTAKE_BLOCKED=" + str(error),file=sys.stderr,flush=True)
        raise SystemExit(1)
