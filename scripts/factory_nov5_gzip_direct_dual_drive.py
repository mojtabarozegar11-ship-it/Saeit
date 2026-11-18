#!/usr/bin/env python3
"""Explicit compressed historical backup transport. Factory stays OFF.

Copies the existing exact gzip (not raw SQL) over pinned SSH, verifies both
compressed and decompressed original digests, then seals the unchanged gzip
inside the existing authenticated F01V2 encrypted parts. No source staging,
deletion, service startup, billing or plaintext cloud upload.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import secrets
import shlex
import subprocess
import tempfile
from contextlib import nullcontext

from scripts import factory_cpanel_existing_nov5_two_drive as legacy
from scripts.factory_dual_stream_v2 import encrypt_stream_to_dual_stores
from scripts.factory_rclone_dual_parts import RcloneDualStore, TransferHold, MAX_MANIFEST_BYTES
from scripts.factory_owner_drive_setup import _validate_owner_oauth_config
from scripts.factory_rclone_ephemeral_binary import provision_verified_rclone

SOURCES = {
    "nov5-a": (279659980, "591a0b10b2f782cb7cb8db3fa340f4b3827b8d1db2960ca89a507098ccc35c78"),
    "nov5-b": (279659148, "4d416f38744023293864d051b511d2ce957004b5c91ebc9882722f5486e31811"),
}
CHUNK_BYTES = legacy.CHUNK_BYTES
RESERVE = legacy.MIN_FREE_RESERVE


def pair_required_bytes():
    return RESERVE + sum(n + ((n + CHUNK_BYTES - 1)//CHUNK_BYTES)*64 + MAX_MANIFEST_BYTES
                         for n, _ in SOURCES.values())


REMOTE = r'''
import hashlib,os,pathlib,pwd,stat,sys,zlib
home=pathlib.Path("/home/zomorod2")
root=home/"restore-staging"/"factory"
catalog={
"master-before-20261105T154953Z.sqlite3.gz":(279659980,"591a0b10b2f782cb7cb8db3fa340f4b3827b8d1db2960ca89a507098ccc35c78","a9fd2175f9ace1a81d67cf7145e54b8621fd44cc06b0b2739bdc9345e21750e2"),
"master-before-20261105T210434Z.sqlite3.gz":(279659148,"4d416f38744023293864d051b511d2ce957004b5c91ebc9882722f5486e31811","402c16b67d430132701435eb4b3f79de88cd5c2479bb07c741c6674708a931be")}
if len(sys.argv)!=2 or sys.argv[1] not in catalog:sys.exit(91)
if pwd.getpwuid(os.geteuid()).pw_name!="zomorod2":sys.exit(92)
for d in (home,root.parent,root):
    s=d.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.geteuid() or s.st_mode&0o022:sys.exit(93)
name=sys.argv[1];p=root/name
size,gzsha,rawsha=catalog[name]
for suf in ("-wal","-shm","-journal"):
    side=root/(name[:-3]+suf)
    if side.exists() or side.is_symlink():sys.exit(94)
s=p.lstat()
if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.geteuid() or s.st_nlink!=1 or s.st_mode&0o077 or s.st_size!=size:sys.exit(95)
ident=lambda st:(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)
fd=os.open(p,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
try:
    if ident(os.fstat(fd))!=ident(s):sys.exit(96)
    dec=zlib.decompressobj(31);zh=hashlib.sha256();rh=hashlib.sha256()
    n=rn=0;header=b""
    while True:
        b=os.read(fd,1048576)
        if not b:break
        n+=len(b);zh.update(b)
        if n>size or dec.eof:sys.exit(97)
        rem=b
        while rem:
            plain=dec.decompress(rem,1048576)
            rn+=len(plain);rh.update(plain)
            if rn>1408634880 or dec.unused_data:sys.exit(97)
            header=(header+plain[:16])[:16]
            if len(header)==16 and header!=b"SQLite format 3\x00":sys.exit(97)
            tail=dec.unconsumed_tail
            if (dec.eof and tail) or (tail==rem and not plain):sys.exit(97)
            rem=tail
        view=memoryview(b)
        while view:
            sent=os.write(sys.stdout.fileno(),view)
            if sent<=0:sys.exit(98)
            view=view[sent:]
    if (not dec.eof or dec.unused_data or dec.unconsumed_tail or n!=size or rn!=1408634880
        or zh.hexdigest()!=gzsha or rh.hexdigest()!=rawsha or header!=b"SQLite format 3\x00"
        or ident(os.fstat(fd))!=ident(s) or ident(p.lstat())!=ident(s)):sys.exit(99)
finally:os.close(fd)
'''


class VerifiedCompressedSource(legacy.VerifiedCpanelStream):
    def __init__(self, config, known, snapshot):
        self.expected_bytes, self.expected = SOURCES[snapshot]
        # Reuse the existing pinned SSH command construction, not arbitrary SSH args.
        self.argv = legacy._ssh_command(config, known, snapshot, "stream")
        self.argv[-1] = ("exec nice -n 15 python3 -B -c " + shlex.quote(REMOTE)
                         + " " + shlex.quote(legacy.SOURCES[snapshot][0]+".gz"))
        self.p = None
        self.done = self.verified = False
        self.n = 0
        self.h = hashlib.sha256()

    def read(self, size):
        if self.p is None or self.p.stdout is None:
            raise TransferHold("COMPRESSED_SOURCE_NOT_OPEN")
        if type(size) is not int or not 1 <= size <= CHUNK_BYTES:
            raise TransferHold("UNBOUNDED_COMPRESSED_SOURCE_READ_DENIED")
        if self.done:
            return b""
        try:
            if not select.select([self.p.stdout], [], [], legacy.SOURCE_IDLE_TIMEOUT_SECONDS)[0]:
                raise TransferHold("COMPRESSED_SOURCE_IDLE_TIMEOUT")
            data = os.read(self.p.stdout.fileno(), min(size, 1048576))
        except (OSError, ValueError):
            raise TransferHold("COMPRESSED_SOURCE_PIPE_FAILED") from None
        if data:
            self.n += len(data)
            if self.n > self.expected_bytes:
                raise TransferHold("COMPRESSED_SOURCE_OVERSIZE")
            self.h.update(data)
            return data
        self.done = True
        try:
            rc = self.p.wait(timeout=30)
        except subprocess.TimeoutExpired:
            raise TransferHold("COMPRESSED_SOURCE_TIMEOUT") from None
        if rc or self.n != self.expected_bytes or self.h.hexdigest() != self.expected:
            raise TransferHold("COMPRESSED_SOURCE_NOT_AUTHENTICATED")
        self.verified = True
        return b""


def run(args):
    if os.geteuid()==0:
        raise TransferHold("NONROOT_OWNER_TRANSFER_RUNNER_REQUIRED")
    config=Path(args.rclone_config)
    _validate_owner_oauth_config(config)
    pub=legacy._secure_file(Path(args.public_pem),16384)
    n,sha=SOURCES[args.snapshot]
    with tempfile.TemporaryDirectory(prefix="factory-gzip-rclone-",dir="/tmp") as tmp:
        client=nullcontext(args.rclone_exe) if args.rclone_exe else provision_verified_rclone(Path(tmp))
        with client as binary:
            store=RcloneDualStore(config,remote_a="factory_a",remote_b="factory_b",
                expected_root_a=legacy.GOOGLE_A_ROOT,expected_root_b=legacy.GOOGLE_B_ROOT,
                proof_path=legacy.PROOF_PATH,proof_sha256=legacy.PROOF_SHA256,
                max_source_bytes=n,chunk_bytes=CHUNK_BYTES,free_reserve_bytes=RESERVE,
                rclone_exe=str(binary))
            store.preflight()
            namespace="factory-historical-"+secrets.token_hex(16)
            cb=store.callbacks(namespace,destination_kind="historical-nov5")
            with VerifiedCompressedSource(Path(args.ssh_config),Path(args.known_hosts),args.snapshot) as source:
                receipt=encrypt_stream_to_dual_stores(source,public_pem=pub,
                    trusted_public_spki_sha256=args.trusted_public_spki_sha256,
                    owner_a="owner-a",owner_b="owner-b",upload_a=cb[0],upload_b=cb[1],
                    read_a=cb[2],read_b=cb[3],chunk_bytes=CHUNK_BYTES,max_source_bytes=n)
                if not source.verified or source.n!=n or receipt.plaintext_bytes!=n:
                    raise TransferHold("COMPRESSED_SOURCE_NOT_AUTHENTICATED")
    return {"schema":"factory.historical.gzip.f01v2.receipt.v1",
        "snapshot_id":args.snapshot,"namespace":namespace,"plaintext_format":"gzip",
        "gzip_bytes":n,"gzip_sha256":sha,"original_sqlite_bytes":legacy.SOURCE_BYTES,
        "original_sqlite_sha256":legacy.SOURCES[args.snapshot][1],
        "manifest_sha256":receipt.manifest_sha256,"encrypted_parts":receipt.parts,
        "dual_provider_readback_verified":True,"independent_restore_verified":False,
        "source_deleted":False,"factory_started":False,"current_mariadb_backup":False}


def main():
    p=argparse.ArgumentParser(description="Owner-only existing exact gzip dual Drive transfer")
    p.add_argument("--snapshot",choices=tuple(SOURCES),required=True)
    for arg in ("ssh-config","known-hosts","rclone-config","public-pem","trusted-public-spki-sha256"):
        p.add_argument("--"+arg,required=True)
    p.add_argument("--rclone-exe")
    args=p.parse_args()
    if len(args.trusted_public_spki_sha256)!=64:
        raise TransferHold("OWNER_PUBLIC_KEY_PIN_REQUIRED")
    print(json.dumps(run(args),sort_keys=True),flush=True)


if __name__=="__main__":
    try: main()
    except (TransferHold,ValueError,RuntimeError,OSError):
        raise SystemExit("HOLD: COMPRESSED_TRANSFER_NOT_COMPLETED")
