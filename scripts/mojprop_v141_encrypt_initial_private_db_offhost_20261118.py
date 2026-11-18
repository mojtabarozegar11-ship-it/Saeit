#!/usr/bin/env python3
"""Off-host initial ZERO-CUSTOMER small SQLite backup, encrypted on owner VPS.

Consumes ONLY a capped byte stream from pinned owner cPanel in-memory via
SSH stdin. Never sends raw customer data or credentials to GitHub. Creates
one AES-256/PBKDF2 encrypted file, key restricted to owner VPS, and verifies
an in-memory restore. No production DB, no TRX payment or website writes.
The first backup is of an EMPTY merchant ledger; future customer snapshots
need separately scheduled encryption, replication and key custody review.
"""
from pathlib import Path
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import stat
import subprocess
import sys

BASE=Path.home()/".mojprop-native-v141-offhost-20261118"
CIPHER=BASE/"initial-empty-merchant.sqlite3.aes256"
KEY=BASE/"private-backup-passphrase.key"
MANIFEST=BASE/"initial-empty-backup-manifest.json"
LIMIT=8*1024*1024
REQUIRED={
 "prop_firm_propv141nativeorder","prop_firm_propv141nativereceipt",
 "prop_firm_propglobaltrxsettlement","prop_firm_propv141simstate",
 "prop_firm_propv141virtualbook",
}
report={"schema":"mojprop.private.trx.offhost_first_zero_customer.v1",
 "encrypted_copy_stored":False,"key_private_vps_only":False,
 "initial_sqlite_integrity":False,"in_memory_decrypt_restore_verified":False,
 "all_paid_tables_zero_rows":False,"original_source_database_modified":False,
 "owner_cpanel_app_modified":False,"customer_data_replicated":False,
 "customer_payment_enabled":False,"vps_backend_restart":False,
 "cipher_kib":0}
try:
 if BASE.is_symlink() or any(p.is_symlink() for p in (KEY,CIPHER,MANIFEST)):
  raise RuntimeError("Symlink destination not allowed")
 if BASE.exists():
  raise RuntimeError("Existing archive directory: no overwrite or key rotation")
 raw=sys.stdin.buffer.read(LIMIT+1)
 if not raw or len(raw)>LIMIT or not raw.startswith(b"SQLite format 3\x00"):
  raise RuntimeError("No permitted bounded private SQLite snapshot")
 conn=sqlite3.connect(":memory:")
 conn.deserialize(raw)
 tables={x[0] for x in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
 if not REQUIRED<=tables or conn.execute("PRAGMA integrity_check").fetchone()!=("ok",):
  raise RuntimeError("First SQLite snapshot invalid/incomplete")
 counts=[conn.execute('SELECT count(*) FROM "'+t+'"').fetchone()[0] for t in REQUIRED]
 if any(counts):
  raise RuntimeError("Expected EMPTY first merchant ledger, never export real buyer records")
 report["initial_sqlite_integrity"]=True
 report["all_paid_tables_zero_rows"]=True
 BASE.mkdir(mode=0o700)
 os.chmod(BASE,0o700)
 secret=secrets.token_bytes(32)
 fd=os.open(KEY,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,"wb") as f:
  f.write(secret.hex().encode("ascii")+b"\n")
  f.flush();os.fsync(f.fileno())
 enc=subprocess.run(["openssl","enc","-aes-256-cbc","-pbkdf2",
             "-iter","250000","-salt","-pass","file:"+str(KEY)],
            input=raw,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            timeout=25,check=False)
 if enc.returncode or not enc.stdout.startswith(b"Salted__"):
  raise RuntimeError("OpenSSL AES encrypted backup failed")
 cipher=enc.stdout
 with open(CIPHER,"xb") as f:
  os.chmod(CIPHER,0o600)
  f.write(cipher);f.flush();os.fsync(f.fileno())
 d=hmac.new(secret,cipher,hashlib.sha256).hexdigest()
 dec=subprocess.run(["openssl","enc","-d","-aes-256-cbc","-pbkdf2",
             "-iter","250000","-pass","file:"+str(KEY)],
           input=cipher,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
           timeout=25,check=False)
 if dec.returncode or not hmac.compare_digest(dec.stdout,raw):
  raise RuntimeError("Off-host decryption did not roundtrip")
 recovered=sqlite3.connect(":memory:")
 recovered.deserialize(dec.stdout)
 if (recovered.execute("PRAGMA integrity_check").fetchone()!=("ok",)
    or not REQUIRED<={x[0] for x in recovered.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    or any(recovered.execute('SELECT count(*) FROM "'+t+'"').fetchone()[0]
           for t in REQUIRED)):
  raise RuntimeError("Recovered off-host database integrity/records mismatch")
 report["in_memory_decrypt_restore_verified"]=True
 manifest={
   "schema":"mojprop.offhost.initial_encrypted_empty.v1",
   "cipher_sha256":hashlib.sha256(cipher).hexdigest(),
   "hmac_sha256":d,
   "plaintext_size":len(raw),
   "cipher_size":len(cipher),
   "encryption":"OpenSSL aes-256-cbc pbkdf2 250000 + independent HMAC-SHA256",
   "source":"owner-cpanel-private-empty-sqlite",
   "source_revision":"a07c6a69847732087fefd3116806a2b2a57037b0",
   "all_paid_tables_empty":True,
 }
 fd=os.open(MANIFEST,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,"w",encoding="utf8") as f:
  json.dump(manifest,f,sort_keys=True);f.write("\n");f.flush();os.fsync(f.fileno())
 report["encrypted_copy_stored"]=CIPHER.is_file() and MANIFEST.is_file()
 report["key_private_vps_only"]=all(stat.S_IMODE(x.stat().st_mode)==0o600
    for x in (KEY,CIPHER,MANIFEST)) and stat.S_IMODE(BASE.stat().st_mode)==0o700
 report["cipher_kib"]=(len(cipher)+1023)//1024
except Exception as e:
 report["error_kind"]=type(e).__name__
 report["error_summary"]=str(e).replace(str(BASE),"<private-vps-backup>")[:150]
finally:
 print("MOJPROP_INITIAL_OFFHOST_ENCRYPTED_DB="+json.dumps(report,sort_keys=True))
if not (report["encrypted_copy_stored"] and report["key_private_vps_only"]
        and report["in_memory_decrypt_restore_verified"]):
 raise SystemExit(1)
