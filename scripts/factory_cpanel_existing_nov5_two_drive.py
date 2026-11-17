#!/usr/bin/env python3
"""Off-only transfer of ONE preexisting, immutable cPanel Nov-05 SQLite snapshot.

NO factory start, SQL connection, fresh dump, cron, customer code imports,
source alteration, source delete, restore, overwrite or paid cloud provisioning.

Cloud OAuth must be present IN the owner's pinned transfer runner already.
A/B proofs, individual free quota and exact encrypted read-back precede
completion. Remote cPanel Python streams one immutable allowlisted file over
pinned SSH; data is encrypted on the runner without a disk staging file.
This script never declares a source safe to delete (independent restore gate).
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import pwd
import secrets
import shlex
import shutil
import stat
import subprocess
import sys
from typing import BinaryIO

from scripts.factory_dual_stream_v2 import encrypt_stream_to_dual_stores
from scripts.factory_rclone_dual_parts import RcloneDualStore, TransferHold

OWNER_ROOT = "/home/zomorod2/restore-staging/factory"
SOURCES = {
    "nov5-a": (
        "master-before-20261105T154953Z.sqlite3",
        "a9fd2175f9ace1a81d67cf7145e54b8621fd44cc06b0b2739bdc9345e21750e2",
    ),
    "nov5-b": (
        "master-before-20261105T210434Z.sqlite3",
        "402c16b67d430132701435eb4b3f79de88cd5c2479bb07c741c6674708a931be",
    ),
}
SOURCE_BYTES = 1408634880
GOOGLE_A_ROOT = "191sAkv4A01S9o6zhx-vM5xM7WO31qHPn"
GOOGLE_B_ROOT = "1e6D3Ek4k-4JT_oyEoiY_JejErZFssrC_"
PROOF_PATH = "F-01 Factory VPS encrypted recovery 2026-10-30/manifest.json"
PROOF_SHA256 = "753365e1584a228d4a4b60b1f7bc21dabdf9514dfc1fe362b5257326768233da"
CPANEL_HOST = "[zohal.pws-dns.net]:1396"
PIN_SHA256 = "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04"
CHUNK_BYTES = 8 * 1024 * 1024
MIN_FREE_RESERVE = 1024 * 1024 * 1024

# This string is passed as a shell-quoted python3 -c argument over the already
# pinned owner SSH relay; its only user-supplied value is an allowlisted basename.
# No remote writable temporary files, SQL database connections or app imports.
REMOTE_PY = r'''
import hashlib,json,os,pathlib,pwd,stat,sys
root=pathlib.Path("/home/zomorod2/restore-staging/factory")
allowed={
"master-before-20261105T154953Z.sqlite3": "a9fd2175f9ace1a81d67cf7145e54b8621fd44cc06b0b2739bdc9345e21750e2",
"master-before-20261105T210434Z.sqlite3": "402c16b67d430132701435eb4b3f79de88cd5c2479bb07c741c6674708a931be"
}
if len(sys.argv)!=3 or sys.argv[1] not in allowed or sys.argv[2] not in ("probe","stream"): sys.exit(91)
if pwd.getpwuid(os.geteuid()).pw_name!="zomorod2": sys.exit(92)
name,mode=sys.argv[1:3]
home=pathlib.Path("/home/zomorod2")
for d in (home,home/"restore-staging",root):
    st=d.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid!=os.geteuid() or st.st_mode&0o022: sys.exit(93)
p=root/name
st=p.lstat()
if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.geteuid() or st.st_nlink!=1 or st.st_size!=1408634880: sys.exit(94)
for suffix in ("-wal","-shm","-journal"):
    if (root/(name+suffix)).exists() or (root/(name+suffix)).is_symlink(): sys.exit(95)
if mode=="probe":
    sys.stdout.write(json.dumps({"schema":"factory.immutable.cpanel.nov5.probe.v1",
      "size":st.st_size,"owner_regular":True,"no_sidecars":True},sort_keys=True)+"\n")
    sys.exit(0)
fd=os.open(p,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
try:
    pre=os.fstat(fd)
    attrs=("st_dev","st_ino","st_size","st_mtime_ns","st_ctime_ns")
    if any(getattr(st,a)!=getattr(pre,a) for a in attrs): sys.exit(96)
    h=hashlib.sha256();count=0
    if os.read(fd,16)!=b"SQLite format 3\x00":sys.exit(97)
    os.lseek(fd,0,os.SEEK_SET)
    while True:
        block=os.read(fd,1048576)
        if not block:break
        h.update(block);count+=len(block)
        view=memoryview(block)
        while view:
            n=os.write(sys.stdout.fileno(),view)
            if n<=0:sys.exit(98)
            view=view[n:]
    post=os.fstat(fd)
    if (count!=1408634880 or
        any(getattr(pre,a)!=getattr(post,a) for a in attrs) or
        h.hexdigest()!=allowed[name]): sys.exit(99)
finally: os.close(fd)
'''


def _secure_file(path: Path, max_bytes: int) -> bytes:
    if not path.is_absolute():
        raise TransferHold("OWNER_FILE_MUST_BE_ABSOLUTE")
    try:
        s = path.lstat()
        if (not stat.S_ISREG(s.st_mode) or s.st_uid != os.geteuid() or
                s.st_nlink != 1 or s.st_mode & 0o077 or
                not 0 < s.st_size <= max_bytes):
            raise TransferHold("OWNER_FILE_NOT_SECURE")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            current = os.fstat(fd)
            if (current.st_ino, current.st_size, current.st_mtime_ns) != (
                    s.st_ino, s.st_size, s.st_mtime_ns):
                raise TransferHold("OWNER_FILE_CHANGED")
            data = os.read(fd, max_bytes + 1)
            if len(data) != s.st_size:
                raise TransferHold("OWNER_FILE_CHANGED")
            return data
        finally:
            os.close(fd)
    except TransferHold:
        raise
    except OSError:
        raise TransferHold("OWNER_FILE_UNAVAILABLE") from None


def _verify_cpanel_known_host(raw: bytes) -> None:
    found = []
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith(b"#"):
            continue
        parts = line.split()
        if len(parts) != 3:
            raise TransferHold("CPANEL_KNOWN_HOSTS_AMBIGUOUS")
        host, kind, b64 = parts
        if host != CPANEL_HOST.encode() or kind != b"ssh-ed25519":
            raise TransferHold("CPANEL_KNOWN_HOSTS_UNEXPECTED_ENTRY")
        try:
            key = base64.b64decode(b64, validate=True)
        except (ValueError, base64.binascii.Error):
            raise TransferHold("CPANEL_HOST_KEY_BAD_BASE64") from None
        fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(key).digest()).decode().rstrip("=")
        found.append(fingerprint)
    if found != [PIN_SHA256]:
        raise TransferHold("CPANEL_HOST_FINGERPRINT_MISMATCH")


def _ssh_command(config: Path, known: Path, snapshot: str, mode: str) -> list[str]:
    if snapshot not in SOURCES or mode not in ("probe", "stream"):
        raise TransferHold("UNAPPROVED_SOURCE_OR_MODE")
    if not _secure_file(config, 131072):
        raise TransferHold("UNSAFE_SSH_CONFIG")
    _verify_cpanel_known_host(_secure_file(known, 8192))
    ssh = shutil.which("ssh")
    if not ssh or not os.path.isabs(ssh):
        raise TransferHold("OWNER_SSH_NOT_INSTALLED")
    name = SOURCES[snapshot][0]
    cmd = ("exec python3 -B -c " + shlex.quote(REMOTE_PY) +
           " " + shlex.quote(name) + " " + shlex.quote(mode))
    return [ssh, "-T", "-F", str(config),
            "-o", "StrictHostKeyChecking=yes",
            "-o", "UserKnownHostsFile=" + str(known),
            "-o", "GlobalKnownHostsFile=/dev/null",
            "-o", "BatchMode=yes", "-o", "ForwardAgent=no",
            "-o", "IdentitiesOnly=yes", "-o", "RequestTTY=no",
            "-o", "ServerAliveInterval=20", "-o", "ServerAliveCountMax=3",
            "saeit-cpanel", cmd]


def probe_source(config: Path, known: Path, snapshot: str) -> dict:
    command = _ssh_command(config, known, snapshot, "probe")
    try:
        proc = subprocess.run(command, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise TransferHold("CPANEL_METADATA_PROBE_FAILED") from None
    if proc.returncode or len(proc.stdout) > 512:
        raise TransferHold("CPANEL_METADATA_PROBE_FAILED")
    try:
        data = json.loads(proc.stdout)
        if (type(data) is not dict or set(data) !=
                {"schema", "size", "owner_regular", "no_sidecars"} or
                data["schema"] != "factory.immutable.cpanel.nov5.probe.v1" or
                type(data["size"]) is not int or data["size"] != SOURCE_BYTES or
                data["owner_regular"] is not True or data["no_sidecars"] is not True):
            raise ValueError()
        return data
    except (ValueError, UnicodeError, TypeError):
        raise TransferHold("CPANEL_METADATA_NOT_VERIFIED") from None


class VerifiedCpanelStream:
    """No false EOF: SHA + fixed byte count + remote exit checked before seal."""
    def __init__(self, config: Path, known: Path, snapshot: str):
        self.expected = SOURCES[snapshot][1]
        self.argv = _ssh_command(config, known, snapshot, "stream")
        self.p = None
        self.done = False
        self.verified = False
        self.n = 0
        self.h = hashlib.sha256()

    def __enter__(self):
        try:
            self.p = subprocess.Popen(self.argv, stdin=subprocess.DEVNULL,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL, close_fds=True)
        except OSError:
            raise TransferHold("CPANEL_READONLY_STREAM_UNAVAILABLE") from None
        return self

    def read(self, size: int) -> bytes:
        if self.p is None or self.p.stdout is None:
            raise TransferHold("CPANEL_STREAM_NOT_OPEN")
        if type(size) is not int or not 1 <= size <= CHUNK_BYTES:
            raise TransferHold("UNBOUNDED_SOURCE_READ_DENIED")
        if self.done:
            return b""
        try:
            data = self.p.stdout.read(size)
        except OSError:
            raise TransferHold("CPANEL_SOURCE_PIPE_FAILURE") from None
        if type(data) is not bytes:
            raise TransferHold("CPANEL_NONBINARY_SOURCE")
        if data:
            self.n += len(data)
            if self.n > SOURCE_BYTES:
                raise TransferHold("CPANEL_SOURCE_TOO_LARGE")
            self.h.update(data)
            return data
        self.done = True
        try:
            rc = self.p.wait(timeout=30)
        except subprocess.TimeoutExpired:
            raise TransferHold("CPANEL_SOURCE_PROCESS_TIMEOUT") from None
        if rc != 0 or self.n != SOURCE_BYTES or self.h.hexdigest() != self.expected:
            raise TransferHold("CPANEL_SNAPSHOT_INTEGRITY_OR_SOURCE_CHANGED")
        self.verified = True
        return b""

    def __exit__(self, exc_type, exc, tb):
        if self.p is not None:
            if self.p.poll() is None:
                self.p.kill()
            try:
                self.p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                raise TransferHold("CPANEL_SOURCE_PROCESS_REAP_TIMEOUT") from None
            if self.p.stdout is not None:
                self.p.stdout.close()
        return False


def run_export(args):
    # This program never runs as root or under the target cPanel account.
    identity = pwd.getpwuid(os.geteuid()).pw_name
    if identity != "githubops":
        raise TransferHold("OWNER_FACTORY_RUNNER_ONLY")
    config,known=Path(args.ssh_config),Path(args.known_hosts)
    p = probe_source(config, known, args.snapshot)
    if args.mode == "probe":
        return {"schema":"factory.cpanel.nov5.off-only.v1","mode":"probe",
                "snapshot_id":args.snapshot,"source_metadata_verified":True,
                "expected_source_bytes":p["size"],"backup_uploaded":False,
                "factory_started":False,"source_deleted":False,
                "source_contents_read":False,"safe_to_delete":False}
    # Gated provider OAuth/2-root proof/free quota BEFORE remote source opens.
    pub = _secure_file(Path(args.public_pem), 16384)
    transport = RcloneDualStore(
        Path(args.rclone_config), remote_a="factory_a", remote_b="factory_b",
        expected_root_a=GOOGLE_A_ROOT, expected_root_b=GOOGLE_B_ROOT,
        proof_path=PROOF_PATH, proof_sha256=PROOF_SHA256,
        max_source_bytes=SOURCE_BYTES, chunk_bytes=CHUNK_BYTES,
        free_reserve_bytes=MIN_FREE_RESERVE,rclone_exe=args.rclone_exe)
    admission = transport.preflight()
    namespace = "factory-current-" + secrets.token_hex(16)
    callbacks = transport.callbacks(namespace)
    with VerifiedCpanelStream(config, known, args.snapshot) as source:
        receipt = encrypt_stream_to_dual_stores(
            source, public_pem=pub,
            trusted_public_spki_sha256=args.trusted_public_spki_sha256,
            owner_a="owner-a",owner_b="owner-b",
            upload_a=callbacks[0],upload_b=callbacks[1],
            read_a=callbacks[2],read_b=callbacks[3],
            chunk_bytes=CHUNK_BYTES,max_source_bytes=SOURCE_BYTES)
        if not source.verified or source.n != SOURCE_BYTES:
            raise TransferHold("SOURCE_NOT_AUTHENTICATED")
    return {"schema":"factory.cpanel.nov5.off-only.v1","mode":"transfer",
            "snapshot_id":args.snapshot,"source_metadata_verified":True,
            "source_sha256_verified":True,"source_bytes":SOURCE_BYTES,
            "encrypted_parts":receipt.parts,
            "encrypted_bytes":receipt.ciphertext_bytes,
            "manifest_sha256":receipt.manifest_sha256,
            "remote_two_provider_exact_readback":True,
            "provider_quota_preflight_verified":True,
            "factory_started":False,"source_deleted":False,
            "independent_isolated_restore_verified":False,
            "safe_to_delete":False,
            "backup_uploaded":True}


def main(argv=None):
    ap=argparse.ArgumentParser(description="Existing cPanel historical backup transfer; factory stays OFF")
    ap.add_argument("--mode",choices=("probe","transfer"),required=True)
    ap.add_argument("--snapshot",choices=tuple(SOURCES),required=True)
    ap.add_argument("--ssh-config",required=True)
    ap.add_argument("--known-hosts",required=True)
    ap.add_argument("--rclone-config")
    ap.add_argument("--rclone-exe")
    ap.add_argument("--public-pem")
    ap.add_argument("--trusted-public-spki-sha256")
    args=ap.parse_args(argv)
    if args.mode=="transfer":
        if (not args.rclone_config or not args.public_pem or
            not args.trusted_public_spki_sha256 or len(args.trusted_public_spki_sha256)!=64):
            raise TransferHold("MISSING_ENCRYPTION_OR_OWNER_PROVIDER_PREREQUISITES")
    return run_export(args)


if __name__=="__main__":
    try:
        result=main()
        print("FACTORY_CPANEL_EXISTING_BACKUP_TRANSFER="+
              json.dumps(result,sort_keys=True,separators=(",",":")),flush=True)
    except (TransferHold,ValueError,RuntimeError,FileNotFoundError) as exc:
        # Never echo raw parameters, provider stderr, key paths or OS exceptions.
        code=exc.args[0] if isinstance(exc,TransferHold) else "TRANSFER_ABORTED"
        print("FACTORY_CPANEL_EXISTING_BACKUP_HOLD="+str(code),flush=True)
        sys.exit(2)
