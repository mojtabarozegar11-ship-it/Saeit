#!/usr/bin/env python3
"""Portable authenticated streaming encryption of a backup file.

The *public* RSA key encrypts the random AES-256 key; only the separately
protected, password-encrypted private RSA key can recover it. The private key
or password must NEVER be placed in public git, logs, or CI artifacts.

Decrypted outputs are for offline/isolation only, NOT direct live DB restore.
"""
import argparse
import base64
import hashlib
import json
import os
import pathlib
import secrets
import sqlite3
import struct
import sys

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MAGIC=b'F01ENC-RSA3072-AES256GCM-V1\n'
CHUNK=1024*1024
HEADER_MAX=8*1024
MAX_SOURCE_SIZE=3*1024**3


def _public(path):
    key=serialization.load_pem_public_key(pathlib.Path(path).read_bytes())
    if key.key_size < 3072: raise ValueError('WEAK_RSA_PUBLIC_KEY')
    return key


def encrypt(input_path, output_path, public_key_path, rate_bytes_per_sec=0):
    src=pathlib.Path(input_path); dest=pathlib.Path(output_path)
    if src.resolve() == dest.resolve(): raise ValueError('INPUT_EQUALS_OUTPUT')
    flags=os.O_RDONLY | getattr(os,'O_NOFOLLOW',0)
    fd=os.open(src,flags)
    try:
        fstat=os.fstat(fd)
        if not __import__('stat').S_ISREG(fstat.st_mode):raise ValueError('SOURCE_NOT_REGULAR')
        if not 1<=fstat.st_size<=MAX_SOURCE_SIZE:raise ValueError('INVALID_SOURCE_SIZE')
        pub=_public(public_key_path)
        key=secrets.token_bytes(32)
        nonce=secrets.token_bytes(12)
        wrapped=pub.encrypt(key,padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
        header=json.dumps({'schema':'f01-encrypted-offhost.v1','wrapped_key':base64.b64encode(wrapped).decode('ascii'),
                           'nonce':base64.b64encode(nonce).decode('ascii'),'cipher':'AES-256-GCM',
                           'kek':'RSA-OAEP-SHA256','plain_size':fstat.st_size},
                          sort_keys=True,separators=(',',':')).encode()
        if len(header)>HEADER_MAX: raise ValueError('HEADER_TOO_LARGE')
        prefix=MAGIC+struct.pack('>I',len(header))+header
        enc=Cipher(algorithms.AES(key),modes.GCM(nonce)).encryptor()
        enc.authenticate_additional_data(prefix)
        digest=hashlib.sha256()
        out_fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
        count=0
        try:
            with os.fdopen(fd,'rb',closefd=False) as inp,os.fdopen(out_fd,'wb') as out:
                out.write(prefix);digest.update(prefix)
                import time
                started=time.monotonic()
                while True:
                    chunk=inp.read(CHUNK)
                    if not chunk:break
                    count+=len(chunk)
                    if count>fstat.st_size: raise ValueError('SOURCE_GREW_DURING_STREAM')
                    encrypted=enc.update(chunk)
                    out.write(encrypted);digest.update(encrypted)
                    if rate_bytes_per_sec>0:
                        wait=count/rate_bytes_per_sec-(time.monotonic()-started)
                        if wait>0:time.sleep(wait)
                encrypted=enc.finalize()
                out.write(encrypted);digest.update(encrypted)
                tag=enc.tag
                out.write(tag);digest.update(tag)
                out.flush();os.fsync(out.fileno())
            after=os.stat(src,follow_symlinks=False)
            if count!=fstat.st_size or after.st_size!=fstat.st_size or after.st_mtime_ns!=fstat.st_mtime_ns:
                raise ValueError('SOURCE_CHANGED_DURING_STREAM')
            return {'schema':'f01-encrypted-offhost.v1','status':'ENCRYPTED_ARCHIVE_CREATED',
                    'cipher_sha256':digest.hexdigest(),'plaintext_bytes':count,
                    'ciphertext_bytes':dest.stat().st_size,'private_key_disclosed':False}
        except BaseException:
            dest.unlink(missing_ok=True)
            raise
    finally:os.close(fd)


def decrypt(input_path,output_path,private_path,password):
    src=pathlib.Path(input_path);dest=pathlib.Path(output_path)
    if dest.exists(): raise FileExistsError('OUTPUT_EXISTS')
    private=serialization.load_pem_private_key(pathlib.Path(private_path).read_bytes(),password=password)
    with open(src,'rb') as inp:
        if inp.read(len(MAGIC))!=MAGIC:raise ValueError('MAGIC_MISMATCH')
        lengthbytes=inp.read(4)
        if len(lengthbytes)!=4:raise ValueError('INVALID_HEADER_LENGTH')
        n=struct.unpack('>I',lengthbytes)[0]
        if n>HEADER_MAX:raise ValueError('OVERLARGE_HEADER')
        h=inp.read(n)
        if len(h)!=n:raise ValueError('TRUNCATED_HEADER')
        info=json.loads(h)
        if info.get('schema')!='f01-encrypted-offhost.v1' or info.get('cipher')!='AES-256-GCM':raise ValueError('UNKNOWN_FORMAT')
        nonce=base64.b64decode(info['nonce'],validate=True)
        key=private.decrypt(base64.b64decode(info['wrapped_key'],validate=True),padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
        pos=inp.tell();inp.seek(0,2);size=inp.tell()
        if size-pos<16 or size-pos-16!=int(info['plain_size']):raise ValueError('SOURCE_LENGTH_MISMATCH')
        inp.seek(size-16);tag=inp.read(16)
        inp.seek(pos)
        dec=Cipher(algorithms.AES(key),modes.GCM(nonce,tag)).decryptor()
        dec.authenticate_additional_data(MAGIC+lengthbytes+h)
        length=size-pos-16
        try:
            with open(dest,'xb') as out:
                while length>0:
                    x=inp.read(min(CHUNK,length))
                    if not x:raise ValueError('UNEXPECTED_EOF')
                    length-=len(x);out.write(dec.update(x))
                out.write(dec.finalize())
                out.flush();os.fsync(out.fileno())
        except BaseException:
            dest.unlink(missing_ok=True)
            raise
    return {'status':'GCM_AUTHENTICATED','plain_size':dest.stat().st_size,'sqlite_checked':False}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest='mode',required=True)
    e=sub.add_parser('encrypt');e.add_argument('--input',required=True);e.add_argument('--output',required=True);e.add_argument('--public-key',required=True);e.add_argument('--rate-mib',type=float,default=0)
    d=sub.add_parser('decrypt');d.add_argument('--input',required=True);d.add_argument('--output',required=True);d.add_argument('--private-key',required=True);d.add_argument('--passphrase-file',required=True)
    a=ap.parse_args()
    if a.mode=='encrypt':
        if not 0<=a.rate_mib<=100:raise SystemExit('INVALID_RATE')
        result=encrypt(a.input,a.output,a.public_key,int(a.rate_mib*1024**2))
    else:
        passwd=pathlib.Path(a.passphrase_file).read_bytes().strip()
        result=decrypt(a.input,a.output,a.private_key,passwd)
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()