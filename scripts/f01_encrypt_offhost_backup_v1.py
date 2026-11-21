#!/usr/bin/env python3
"""Encrypt bounded regular source directly to an AES-256-GCM artifact.

Public-key-only runner. Never load or store any private key here.
Before applying to real VPS data: ensure external quota, recovery-key custody,
source consistency, I/O throttling, and isolated restore proof are separately gated.
"""
import argparse
import base64
import hashlib
import json
import os
import secrets
import stat
import struct
import sys
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MAGIC=b"F01ENC-RSA3072-AES256GCM-V1\n"
CHUNK=1024*1024
MAX_BYTES=3*1024**3

def encrypt(source, target, recipient, max_mib_sec=0):
    if os.path.realpath(source)==os.path.realpath(target):
        raise ValueError("SAME_SOURCE_DESTINATION")
    pub=serialization.load_pem_public_key(open(recipient,"rb").read())
    if pub.key_size<3072:raise ValueError("INVALID_RSA_STRENGTH")
    fd=os.open(source,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    try:
        st=os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or not 1<=st.st_size<=MAX_BYTES:
            raise ValueError("UNSAFE_SOURCE")
        nonce=secrets.token_bytes(12)
        sym=secrets.token_bytes(32)
        wrapped=pub.encrypt(sym,padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
        header=json.dumps({"schema":"f01-encrypted-offhost.v1","wrapped_key":base64.b64encode(wrapped).decode("ascii"),
                           "nonce":base64.b64encode(nonce).decode("ascii"),"cipher":"AES-256-GCM",
                           "kek":"RSA-OAEP-SHA256","plain_size":st.st_size},
                          sort_keys=True,separators=(",",":")).encode()
        if len(header)>8192:raise ValueError("HEADER_TOO_BIG")
        prefix=MAGIC+struct.pack(">I",len(header))+header
        encryptor=Cipher(algorithms.AES(sym),modes.GCM(nonce)).encryptor()
        encryptor.authenticate_additional_data(prefix)
        sha=hashlib.sha256()
        count=0
        opened=False
        begin=time.monotonic()
        try:
            with open(target,"xb") as output,os.fdopen(fd,"rb",closefd=False) as inp:
                opened=True
                output.write(prefix);sha.update(prefix)
                while True:
                    chunk=inp.read(CHUNK)
                    if not chunk:break
                    count+=len(chunk)
                    if count>st.st_size:raise ValueError("SOURCE_GREW")
                    block=encryptor.update(chunk)
                    output.write(block);sha.update(block)
                    if max_mib_sec:
                        t=count/(max_mib_sec*1024*1024)-(time.monotonic()-begin)
                        if t>0:time.sleep(t)
                final=encryptor.finalize()
                output.write(final);sha.update(final)
                output.write(encryptor.tag);sha.update(encryptor.tag)
                output.flush();os.fsync(output.fileno())
            after=os.stat(source,follow_symlinks=False)
            if count!=st.st_size or after.st_size!=st.st_size or after.st_mtime_ns!=st.st_mtime_ns:
                raise ValueError("SOURCE_CHANGED")
        except BaseException:
            if opened:os.unlink(target)
            raise
        return {"status":"ENCRYPTED","plaintext_bytes":count,"cipher_bytes":os.stat(target).st_size,
                "cipher_sha256":sha.hexdigest(),"unencrypted_backup_uploaded":False}
    finally:
        os.close(fd)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True)
    p.add_argument("--target",required=True)
    p.add_argument("--public-key",required=True)
    p.add_argument("--max-mib-sec",type=float,default=0)
    a=p.parse_args()
    if not 0<=a.max_mib_sec<=100:raise SystemExit("INVALID_RATE")
    print(json.dumps(encrypt(a.source,a.target,a.public_key,a.max_mib_sec),sort_keys=True))

if __name__=="__main__":
    main()
