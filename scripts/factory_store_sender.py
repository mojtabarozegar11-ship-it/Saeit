#!/usr/bin/env python3
"""VPS-local order-free product delivery to cPanel's private inbox over pinned SSH.

No GitHub or ChatGPT dependency at runtime. No payment, Django writes,
public product activation, external commerce or customer orders.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

HOST = "zohal.pws-dns.net"
USER = "zomorod2"
PORT = 1396
HOST_KEY_SHA256 = "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04"
INBOX = "/home/zomorod2/.saeit-factory-inbox"
RECEIVER = INBOX + "/bin/store_receiver.py"
SLUG = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_BUNDLE = 25 * 1024 * 1024


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify_source(manifest_path, archive_path, recipe):
    if not SLUG.fullmatch(recipe):
        raise ValueError("RECIPE_NAME_INVALID")
    if any(p.is_symlink() or not p.is_file() for p in (manifest_path, archive_path)):
        raise ValueError("RECIPE_PATH_UNSAFE")
    if (archive_path.stat().st_size <= 0 or archive_path.stat().st_size > MAX_BUNDLE
            or manifest_path.stat().st_size > 100000):
        raise ValueError("PACKAGE_SIZE_UNSAFE")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("PACKAGE_MANIFEST_INVALID")
    digest = manifest.get("artifact_sha256")
    if not isinstance(digest, str) or not SHA.fullmatch(digest) or digest != sha256(archive_path):
        raise ValueError("PACKAGE_SHA256_MISMATCH")
    if (manifest.get("recipe") != recipe or manifest.get("qa_status") != "passed"
        or manifest.get("commercial_status") != "private_internal_qa_pass_not_published"
        or manifest.get("owner_publication_approval") is not False
        or manifest.get("public_listing_enabled") is not False
        or manifest.get("price") is not None):
        raise ValueError("PACKAGE_NOT_PRIVATE_QA_PASSED")
    return digest


def host_ssh_options(key, known):
    if any(p.is_symlink() or not p.is_file() for p in (key, known)):
        raise ValueError("SSH_IDENTITY_OR_PIN_MISSING")
    if key.stat().st_mode & 0o077:
        raise ValueError("SSH_KEY_PERMISSIONS_UNSAFE")
    checked = subprocess.run(["ssh-keygen", "-lf", str(known), "-E", "sha256"],
                             capture_output=True, text=True, timeout=8, check=True)
    fingerprints = {line.split()[1] for line in checked.stdout.splitlines()
                    if len(line.split()) > 1}
    if fingerprints != {HOST_KEY_SHA256}:
        raise ValueError("CPANEL_HOST_PIN_MISMATCH")
    return ["-i", str(key), "-o", "StrictHostKeyChecking=yes", "-o", "BatchMode=yes",
            "-o", "IdentitiesOnly=yes", "-o", "UserKnownHostsFile=" + str(known),
            "-o", "ConnectTimeout=12"]


def call(command, *, allowed=(0,), timeout=40):
    completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if completed.returncode not in allowed:
        raise RuntimeError("PRODUCT_DELIVERY_COMMAND_FAILED:" + str(completed.returncode))
    return completed


def deliver(recipe, source, ssh_options, *, dry_run=False):
    manifest = source / recipe / "manufacturing_manifest.json"
    archive = source / recipe / (recipe + "-internal-qa.zip")
    digest = verify_source(manifest, archive, recipe)
    remote = USER + "@" + HOST
    receiver_args = ["python3", RECEIVER]
    target = INBOX + "/incoming/" + recipe + "/" + digest
    ssh_base = ["ssh", "-p", str(PORT)] + ssh_options + [remote]
    if dry_run:
        return {"recipe": recipe, "digest": digest, "status": "dry_run_private_only"}
    check = call(ssh_base + [" ".join(receiver_args + [
        "status", recipe, digest, "--root", INBOX])], allowed=(0, 1))
    if check.returncode == 0:
        return {"recipe": recipe, "digest": digest, "status": "already_received"}
    call(ssh_base + [" ".join(receiver_args + [
        "prepare", recipe, digest, "--root", INBOX])])
    for local, suffix in ((archive, ".zip.partial"), (manifest, ".json.partial")):
        scp = ["scp", "-P", str(PORT)] + ssh_options + [
            str(local), remote + ":" + target + suffix]
        call(scp, timeout=65)
    call(ssh_base + [" ".join(receiver_args + [
        "finalize", recipe, digest, "--root", INBOX])])
    receipt = call(ssh_base + [" ".join(receiver_args + [
        "status", recipe, digest, "--root", INBOX])])
    if "STORE_PRIVATE_RECEIPT_VERIFIED" not in receipt.stdout:
        raise RuntimeError("STORE_RECEIPT_NOT_VERIFIED")
    return {"recipe": recipe, "digest": digest, "status": "received_private"}


def sync(source, key, known, *, limit=3, dry_run=False):
    if limit < 1 or limit > 20:
        raise ValueError("LIMIT_OUT_OF_RANGE")
    root = Path(source).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("FACTORY_PRODUCTS_MISSING")
    options = host_ssh_options(Path(key).expanduser(), Path(known).expanduser())
    products = sorted(p.name for p in root.iterdir()
                      if p.is_dir() and not p.is_symlink() and SLUG.fullmatch(p.name))[:limit]
    return [deliver(recipe, root, options, dry_run=dry_run) for recipe in products]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--products", required=True)
    parser.add_argument("--ssh-key", required=True)
    parser.add_argument("--known-hosts", required=True)
    parser.add_argument("--max-products", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    results = sync(args.products, args.ssh_key, args.known_hosts,
                   limit=args.max_products, dry_run=args.dry_run)
    for item in results:
        print("FACTORY_STORE_PRODUCT=" + item["recipe"])
        print("FACTORY_STORE_DELIVERY=" + item["status"])
    print("FACTORY_STORE_TRANSFER_COUNT=" + str(len(results)))
    print("FACTORY_STORE_ORDERS_REQUIRED=false")
    print("FACTORY_STORE_PUBLIC_LISTING_ENABLED=false")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print("FACTORY_STORE_DELIVERY_FAILED=" + type(exc).__name__, file=sys.stderr)
        sys.exit(1)
