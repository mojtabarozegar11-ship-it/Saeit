#!/usr/bin/env python3
"""Offline QA of safe owner credential rotation, without real credentials."""
from __future__ import annotations
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parent.parent
SCRIPT=ROOT/"scripts/zomorod_owner_password_rotate.php"
USER="synthetic_owner"
NEW="SyntheticStrongPasswordOnlyForQA2026!"
WEAK="ShortTest12"

def cli(command: str, directory: Path, secret: str | None = None):
    return subprocess.run(["php",str(SCRIPT),command,str(directory),USER],
                          input=None if secret is None else (secret+"\n").encode(),
                          capture_output=True,timeout=20)

with tempfile.TemporaryDirectory(prefix="zm-credentials-synthetic-") as temporary:
    root=Path(temporary)
    private=root/".private"
    folder=private/"zomorod-business"
    private.mkdir(mode=0o700);folder.mkdir(mode=0o700)
    dbfile=folder/"management.sqlite3"
    with sqlite3.connect(dbfile) as db:
        db.executescript("""
            CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT UNIQUE,
                role TEXT NOT NULL, active INTEGER NOT NULL, password_hash TEXT NOT NULL);
            CREATE TABLE audit_events(id INTEGER PRIMARY KEY,user_id INTEGER,
                verb TEXT NOT NULL,subject TEXT NOT NULL,entity_id INTEGER);
        """)
        db.execute("INSERT INTO users(username,role,active,password_hash) VALUES(?,?,?,?)",
                   (USER,"admin",1,"synthetic-preexisting-hash"))
    os.chmod(dbfile,0o600)
    status=cli("inspect",folder)
    assert status.returncode==0 and b"FOUND_ACTIVE_ADMIN" in status.stdout,(status.returncode,status.stderr)
    assert cli("rotate",folder,WEAK).returncode != 0,"weak_password_accepted"
    with sqlite3.connect(dbfile) as db:
        assert db.execute("SELECT password_hash FROM users").fetchone()[0]=="synthetic-preexisting-hash"
        assert db.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]==0
    rotated=cli("rotate",folder,NEW)
    assert rotated.returncode==0,(rotated.returncode,rotated.stderr)
    assert NEW.encode() not in rotated.stdout + rotated.stderr
    with sqlite3.connect(dbfile) as db:
        actual_hash=db.execute("SELECT password_hash FROM users").fetchone()[0]
        assert actual_hash.startswith("$2y$") and NEW not in actual_hash
        assert db.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]==1
        assert db.execute("SELECT verb,subject FROM audit_events").fetchone()==(
            "security","owner-password-rotated-cli")
    check=subprocess.run(["php","-r",
            "exit(password_verify(stream_get_contents(STDIN),$argv[1])?0:4);",actual_hash],
            input=NEW.encode(),capture_output=True,timeout=10)
    assert check.returncode==0,"bcrypt_password_verify_failed"
    assert cli("rotate",folder,NEW).returncode!=0,"same_password_reused"
    assert cli("rotate",folder,NEW).returncode!=0,"second_rotation_same_password"
    assert cli("inspect",folder).returncode==0
    os.chmod(dbfile,0o644)
    assert cli("rotate",folder,"AnotherStrongSyntheticPassword2026!").returncode!=0
    os.chmod(dbfile,0o600)
    fake=private/"alias"
    fake.symlink_to(folder,target_is_directory=True)
    assert cli("inspect",fake).returncode!=0
    with sqlite3.connect(dbfile) as db:
        db.execute("UPDATE users SET active=0")
    assert cli("rotate",folder,"AnotherStrongSyntheticPassword2026!").returncode!=0
    with sqlite3.connect(dbfile) as db:
        assert db.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]==1
print("OWNER_CREDENTIALS_SYNTHETIC_QA=PASS")
print("WEAK_PASSWORD_DENIED=PASS ADMIN_ROLE_GUARD=PASS")
print("PRIVATE_PATH_PERMISSIONS=PASS ONE_TIME_AUDIT=PASS")
print("PASSWORD_ROTATION_HAS_NO_LIVE_COMPANY_DATA=PASS")
