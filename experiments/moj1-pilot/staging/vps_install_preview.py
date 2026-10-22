#!/usr/bin/env python3
"""Private, versioned, fail-closed MOJ1 preview installer. Never reads wallets or live sites."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import tarfile
import tempfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.request import urlopen

BASENAME = ".local/share/moj1-mpw-private-preview-20261022"
DATA = ("index.html", "synthetic-receipt.json", "release-gates.json", "SHA256SUMS")
SHA = re.compile(r"[a-f0-9]{40}\Z")
RUN = re.compile(r"[0-9]{8,16}\Z")

def ensure_private_dir(path, create=False):
    if create:
        path.mkdir(mode=0o700, parents=False, exist_ok=False)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise RuntimeError("UNSAFE_DIRECTORY_OWNER_OR_TYPE")
    if stat.S_IMODE(info.st_mode) != 0o700:
        raise RuntimeError("UNSAFE_DIRECTORY_PERMISSIONS")

def root_path():
    home = Path.home()
    for parent in (home / ".local", home / ".local/share"):
        if parent.is_symlink() or not parent.is_dir():
            raise RuntimeError("UNSAFE_HOME_LOCAL_PATH")
    return home / BASENAME

def prepare(root, run):
    if not RUN.fullmatch(run):
        raise RuntimeError("RUN_ID_INVALID")
    ensure_private_dir(root, create=not root.exists() and not root.is_symlink())
    inbox = root / "inbox"
    ensure_private_dir(inbox, create=not inbox.exists() and not inbox.is_symlink())
    stage = inbox / run
    ensure_private_dir(stage, create=True)
    print("MOJ1_PRIVATE_INBOX=READY")

def payload_from_tar(archive):
    info = archive.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > 1024 * 1024:
        raise RuntimeError("ARCHIVE_UNSAFE")
    with tarfile.open(archive, "r:") as tf:
        members = tf.getmembers()
        if len(members) != len(DATA) or {x.name for x in members} != set(DATA):
            raise RuntimeError("ARCHIVE_MEMBERS_INVALID")
        if any(not x.isfile() or x.size > 256 * 1024 for x in members):
            raise RuntimeError("ARCHIVE_MEMBER_TYPE_OR_SIZE_INVALID")
        files = {item.name: tf.extractfile(item).read() for item in members}
    hashes = {}
    for line in files["SHA256SUMS"].decode("ascii").splitlines():
        part = line.split("  ")
        if len(part) != 2 or not re.fullmatch(r"[a-f0-9]{64}", part[0]) or part[1] in hashes:
            raise RuntimeError("HASH_MANIFEST_INVALID")
        hashes[part[1]] = part[0]
    if set(hashes) != set(DATA) - {"SHA256SUMS"}:
        raise RuntimeError("HASH_MANIFEST_INCOMPLETE")
    for name, digest in hashes.items():
        if hashlib.sha256(files[name]).hexdigest() != digest:
            raise RuntimeError("HASH_MISMATCH_" + name)
    if b'data-testnet-only="true"' not in files["index.html"] or b'data-synthetic-only="true"' not in files["index.html"]:
        raise RuntimeError("NOT_A_SYNTHETIC_TESTNET_PAGE")
    if any(tag in files["index.html"].lower() for tag in (b"<script", b"<form", b"<input", b"<iframe")):
        raise RuntimeError("INTERACTIVE_PAYMENT_SURFACE_FORBIDDEN")
    receipt = json.loads(files["synthetic-receipt.json"])
    gates = json.loads(files["release-gates.json"])
    if (receipt.get("status") != "PASS" or receipt.get("orderKind") != "SYNTHETIC_ONLY" or
        receipt.get("tokenNetwork") != "Shasta" or receipt.get("paymentMethod") != "UNAVAILABLE" or
        receipt.get("orderState") != "NOT_A_REAL_ORDER"):
        raise RuntimeError("RECEIPT_NOT_SYNTHETIC")
    for key in ("paymentEnabled", "deliveryEnabled", "orderWriteEnabled",
                "mainnetEnabled", "keysUsed", "realMojPlayWinGatewayChanged"):
        if receipt.get(key) is not False:
            raise RuntimeError("UNSAFE_RECEIPT_" + key)
    for key in ("readyForMainnet", "publicSaleApproved", "realPaymentEnabled",
                "independentSecurityAuditApproved", "legalReleaseApproved", "mainnetCustodyApproved"):
        if gates.get(key) is not False:
            raise RuntimeError("UNSAFE_RELEASE_GATE_" + key)
    if gates.get("environment") != "ISOLATED_GITHUB_ACTIONS_PREVIEW":
        raise RuntimeError("RELEASE_ENVIRONMENT_MISMATCH")
    return files

def smoke_http(release, expected):
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(release)))
    thread = Thread(target=server.serve_forever, daemon=True)
    try:
        thread.start()
        with urlopen("http://127.0.0.1:" + str(server.server_port) + "/", timeout=5) as response:
            data = response.read(256 * 1024)
            if response.status != 200 or data != expected:
                raise RuntimeError("LOCALHOST_PREVIEW_READBACK_MISMATCH")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

def install(root, run, commit):
    if not RUN.fullmatch(run) or not SHA.fullmatch(commit):
        raise RuntimeError("RELEASE_ARGUMENT_INVALID")
    ensure_private_dir(root)
    stage = root / "inbox" / run
    ensure_private_dir(root / "inbox")
    ensure_private_dir(stage)
    archive = stage / "preview.tar"
    files = payload_from_tar(archive)
    releases = root / "releases"
    ensure_private_dir(releases, create=not releases.exists() and not releases.is_symlink())
    release = releases / commit
    if release.exists() or release.is_symlink():
        ensure_private_dir(release)
        for name in DATA:
            existing = release / name
            meta = existing.lstat()
            if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid() or stat.S_IMODE(meta.st_mode) != 0o600:
                raise RuntimeError("RELEASE_FILE_UNSAFE")
            if existing.read_bytes() != files[name]:
                raise RuntimeError("RELEASE_IMMUTABLE_CONTENT_CONFLICT")
    else:
        ensure_private_dir(release, create=True)
        for name in DATA:
            fd = os.open(release / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(files[name])
    smoke_http(release, files["index.html"])
    marker = root / ("CURRENT.stage-" + run)
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as f:
        f.write(commit + "\n")
    os.replace(marker, root / "CURRENT")
    if (root / "CURRENT").read_text("ascii").strip() != commit:
        raise RuntimeError("CURRENT_RELEASE_READBACK_FAILED")
    print("MOJ1_VPS_PRIVATE_PREVIEW=INSTALLED")
    print("MOJ1_VPS_PREVIEW_LOCALHOST_HTTP=PASS")
    print("MOJ1_VPS_PREVIEW_SHA256=" + hashlib.sha256(files["index.html"]).hexdigest())
    print("MOJ1_VPS_WALLET_FILES_ACCESSED=NO")
    print("MOJ1_VPS_LIVE_GATEWAY_MODIFIED=NO")
    print("MOJ1_VPS_PUBLIC_WEB_SERVER_CHANGED=NO")
    print("MOJ1_VPS_MAINNET=DISABLED")

def self_test():
    data = {
        "index.html": b'<!doctype html><body data-testnet-only="true" data-synthetic-only="true">Shasta staging</body>',
        "synthetic-receipt.json": json.dumps({
            "status":"PASS", "orderKind":"SYNTHETIC_ONLY", "tokenNetwork":"Shasta",
            "orderState":"NOT_A_REAL_ORDER", "paymentMethod":"UNAVAILABLE",
            "paymentEnabled":False, "deliveryEnabled":False, "orderWriteEnabled":False,
            "mainnetEnabled":False, "keysUsed":False, "realMojPlayWinGatewayChanged":False
        }).encode(),
        "release-gates.json": json.dumps({
            "environment":"ISOLATED_GITHUB_ACTIONS_PREVIEW",
            **{key:False for key in ("readyForMainnet", "publicSaleApproved", "realPaymentEnabled",
               "independentSecurityAuditApproved", "legalReleaseApproved", "mainnetCustodyApproved")}
        }).encode()
    }
    data["SHA256SUMS"] = "".join(
        hashlib.sha256(v).hexdigest() + "  " + k + "\n" for k,v in data.items()
    ).encode()
    with tempfile.TemporaryDirectory(prefix="moj1-preview-test-") as tmp:
        root = Path(tmp) / "isolated"
        prepare(root, "39730163129")
        stage = root / "inbox" / "39730163129" / "preview.tar"
        with tarfile.open(stage, "w") as tar:
            for k,v in data.items():
                ti = tarfile.TarInfo(k)
                ti.size = len(v)
                tar.addfile(ti, io.BytesIO(v))
        install(root, "39730163129", "a" * 40)
        assert (root / "CURRENT").read_text().strip() == "a" * 40
        bad = root / "inbox" / "39730163129" / "preview.tar"
        with tarfile.open(bad, "w") as tar:
            ti = tarfile.TarInfo("../escape")
            ti.size = 3
            tar.addfile(ti, io.BytesIO(b"bad"))
        try:
            payload_from_tar(bad)
        except RuntimeError as exc:
            assert str(exc) == "ARCHIVE_MEMBERS_INVALID"
        else:
            raise AssertionError("Traversal archive must fail")
    print("MOJ1_PREVIEW_INSTALLER_SELF_TEST=PASS")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "install", "self-test"))
    parser.add_argument("run", nargs="?")
    parser.add_argument("commit", nargs="?")
    args = parser.parse_args()
    if args.action == "self-test":
        self_test()
    elif args.action == "prepare":
        if args.commit is not None or args.run is None:
            parser.error("prepare requires RUN_ID only")
        prepare(root_path(), args.run)
    else:
        if args.run is None or args.commit is None:
            parser.error("install requires RUN_ID and COMMIT_SHA")
        install(root_path(), args.run, args.commit)
