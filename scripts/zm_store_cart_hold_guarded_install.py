#!/usr/bin/env python3
"""Additive, reversible installer for the *disabled* ZM cart landing only.

Never touches products, financial databases, PSP, sessions, or other sites.
Production apply requires explicit CLI confirmation and the pinned home path.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

OWNER_MARK = "zm-store-cart-hold-20261102"
RUN_PATTERN = re.compile(r"[0-9]{5,20}\Z")
SHA_PATTERN = re.compile(r"[a-f0-9]{64}\Z")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def regular(path):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("UNSAFE_FILE:" + str(path))


def directory(path):
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError("UNSAFE_DIRECTORY:" + str(path))


def preflight(home, source, run_id, expected_sha):
    home, source = Path(home), Path(source)
    if not RUN_PATTERN.fullmatch(run_id) or not SHA_PATTERN.fullmatch(expected_sha):
        raise RuntimeError("INVALID_RUN_OR_DIGEST")
    directory(home)
    directory(home / "public_html")
    store = home / "public_html/store"
    directory(store)
    regular(store / "index.php")
    private = home / ".private/zomorod-business"
    directory(home / ".private")
    directory(private)
    regular(source)
    if digest(source) != expected_sha:
        raise RuntimeError("CANDIDATE_DIGEST_MISMATCH")
    body = source.read_text(encoding="utf8")
    for required in ("http_response_code(405)", "form-action 'none'", "no-store",
                     "ثبت سفارش و پرداخت اینترنتی در حال حاضر غیرفعال است"):
        if required not in body:
            raise RuntimeError("CANDIDATE_NOT_HOLD_ONLY")
    check = subprocess.run(["php", "-l", str(source)], capture_output=True,
                           text=True, timeout=10)
    if check.returncode:
        raise RuntimeError("PHP_SYNTAX_INVALID")
    target = store / "cart"
    if target.exists() or target.is_symlink():
        raise RuntimeError("EXISTING_CART_REFUSE_OVERWRITE")
    return store, private, target


def install(home, source, run_id, expected_sha, *, production=True):
    if production and Path(home) != Path("/home/zomorod2"):
        raise RuntimeError("PRODUCTION_HOME_MISMATCH")
    store, private, target = preflight(home, source, run_id, expected_sha)
    lock = private / ".zm-cart-hold-install.lock"
    if lock.is_symlink():
        raise RuntimeError("LOCK_SYMLINK")
    with lock.open("a+b") as handle:
        os.fchmod(handle.fileno(), 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        store, private, target = preflight(home, source, run_id, expected_sha)
        manifest_dir = private / ".zm-cart-hold-releases"
        if manifest_dir.is_symlink():
            raise RuntimeError("MANIFEST_DIR_SYMLINK")
        manifest = manifest_dir / (run_id + ".json")
        if manifest.exists() or manifest.is_symlink():
            raise RuntimeError("MANIFEST_COLLISION")
        manifest_dir.mkdir(mode=0o700, exist_ok=True)
        directory(manifest_dir)
        target.mkdir(mode=0o755)
        installed = False
        try:
            file = target / "index.php"
            with tempfile.NamedTemporaryFile(dir=target, prefix=".zm-cart-", delete=False) as tmp:
                temp = Path(tmp.name)
                with Path(source).open("rb") as stream:
                    shutil.copyfileobj(stream, tmp)
                tmp.flush()
                os.fsync(tmp.fileno())
            try:
                os.chmod(temp, 0o644)
                os.replace(temp, file)
            finally:
                temp.unlink(missing_ok=True)
            installed = True
            if digest(file) != expected_sha:
                raise RuntimeError("INSTALL_DIGEST_MISMATCH")
            (target / ".zm-owner").write_text(OWNER_MARK + "\n", encoding="ascii")
            os.chmod(target / ".zm-owner", 0o600)
            data = {"owner": OWNER_MARK, "run_id": run_id, "sha256": expected_sha,
                    "relative_path": "public_html/store/cart/index.php",
                    "previous_route": "absent", "payment_enabled": False}
            manifest.write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf8")
            os.chmod(manifest, 0o600)
            return data
        except BaseException:
            # Roll back only our newly-created files; never replace an existing cart.
            if installed and (target / "index.php").is_file() and digest(target / "index.php") == expected_sha:
                (target / "index.php").unlink()
            if (target / ".zm-owner").is_file() and (target / ".zm-owner").read_text() == OWNER_MARK + "\n":
                (target / ".zm-owner").unlink()
            if target.exists() and not any(target.iterdir()):
                target.rmdir()
            raise


def rollback(home, run_id, *, production=True):
    if production and Path(home) != Path("/home/zomorod2"):
        raise RuntimeError("PRODUCTION_HOME_MISMATCH")
    home = Path(home)
    private = home / ".private/zomorod-business"
    store = home / "public_html/store"
    directory(private)
    directory(store)
    if not RUN_PATTERN.fullmatch(run_id):
        raise RuntimeError("INVALID_RUN")
    lock = private / ".zm-cart-hold-install.lock"
    regular(lock)
    with lock.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        manifest = private / ".zm-cart-hold-releases" / (run_id + ".json")
        directory(manifest.parent)
        regular(manifest)
        data = json.loads(manifest.read_text(encoding="utf8"))
        target = store / "cart"
        directory(target)
        file, mark = target / "index.php", target / ".zm-owner"
        regular(file)
        regular(mark)
        if (data.get("owner") != OWNER_MARK or data.get("previous_route") != "absent"
                or data.get("relative_path") != "public_html/store/cart/index.php"
                or mark.read_text(encoding="ascii") != OWNER_MARK + "\n"
                or digest(file) != data.get("sha256")
                or set(p.name for p in target.iterdir()) != {"index.php", ".zm-owner"}):
            raise RuntimeError("ROLLBACK_OWNERSHIP_OR_HASH_MISMATCH")
        file.unlink()
        mark.unlink()
        target.rmdir()
        manifest.unlink()
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sha256", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--rollback", action="store_true")
    parser.add_argument("--approval", default="")
    args = parser.parse_args()
    home = Path("/home/zomorod2")
    if args.rollback:
        if args.approval != "ROLLBACK_DISABLED_CART_ONLY":
            raise SystemExit("OWNER_ROLLBACK_APPROVAL_REQUIRED")
        rollback(home, args.run_id)
        print("ZM_CART_HOLD_OWNED_ROLLBACK=PASS")
    elif args.apply:
        if args.approval != "INSTALL_DISABLED_CART_ONLY":
            raise SystemExit("OWNER_RELEASE_APPROVAL_REQUIRED")
        print(json.dumps(install(home, args.source, args.run_id, args.sha256), ensure_ascii=False))
    else:
        preflight(home, args.source, args.run_id, args.sha256)
        print("ZM_CART_HOLD_READONLY_PREFLIGHT=PASS")
