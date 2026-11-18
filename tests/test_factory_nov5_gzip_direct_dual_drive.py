"""Regression checks for exact compressed historical transport, fixtures only."""
import gzip
import hashlib
import os
from pathlib import Path
import pwd
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import factory_nov5_gzip_direct_dual_drive as m


class DirectCompressedSourceTests(unittest.TestCase):
    def test_exact_pair_capacity(self):
        self.assertEqual(m.pair_required_bytes(),1637259608)

    def fixture(self, kind):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);root=home/"restore-staging"/"factory";root.mkdir(parents=True)
            name=m.legacy.SOURCES["nov5-a"][0]+".gz"
            db=home/"fixture.sqlite3"
            with sqlite3.connect(db) as conn:
                conn.execute("CREATE TABLE t (n BLOB)")
                conn.execute("INSERT INTO t VALUES (?)",(b"Q"*2500000,))
            raw=db.read_bytes();gz=gzip.compress(raw,mtime=0)
            p=root/name
            expected=gz
            if kind=="crc":
                gz=gz[:-8]+bytes([gz[-8]^1])+gz[-7:]
            elif kind=="trailing":
                gz=gz+b"junk"
            elif kind=="truncated":
                gz=gz[:-8]
            elif kind=="wrong":
                gz=gzip.compress(raw[:-1]+bytes([raw[-1]^1]),mtime=0)
            p.write_bytes(gz);p.chmod(0o600)
            if kind=="world":p.chmod(0o644)
            if kind=="hardlink":os.link(p,root/"duplicate")
            if kind=="sidecar":(root/(name[:-3]+"-wal")).touch()
            if kind=="symlink":
                q=home/"other.gz";p.rename(q);p.symlink_to(q)
            src=m.REMOTE.replace("/home/zomorod2",str(home)).replace(
                '!="zomorod2"',"!="+repr(pwd.getpwuid(os.geteuid()).pw_name))
            src=src.replace("1408634880",str(len(raw))).replace("279659980",str(len(expected)))
            src=src.replace(m.SOURCES["nov5-a"][1],hashlib.sha256(expected).hexdigest())
            src=src.replace(m.legacy.SOURCES["nov5-a"][1],hashlib.sha256(raw).hexdigest())
            proc=subprocess.run([sys.executable,"-B","-c",src,name],capture_output=True,timeout=15)
            return proc,expected

    def test_exact_original_gzip_retained(self):
        p,gz=self.fixture("valid")
        self.assertEqual(p.returncode,0)
        self.assertEqual(p.stdout,gz)

    def test_corrupt_or_unsafe_source_never_success(self):
        for kind in ("crc","trailing","truncated","wrong","world","hardlink","sidecar","symlink"):
            with self.subTest(kind=kind):
                p,_=self.fixture(kind)
                self.assertNotEqual(p.returncode,0)

    def test_source_reads_fail_closed_on_tamper(self):
        blob=b"fixture-original"
        with patch.dict(m.SOURCES,{"nov5-a":(len(blob),hashlib.sha256(blob).hexdigest())}), \
             patch.object(m.legacy,"_ssh_command",return_value=["unused"]):
            source=m.VerifiedCompressedSource(Path("/none"),Path("/none"),"nov5-a")
        source.argv=[sys.executable,"-c","import sys;sys.stdout.buffer.write(b'fixture-tampered')"]
        with source:
            with self.assertRaises(m.TransferHold):
                while source.read(4096):pass
            self.assertFalse(source.verified)

    def test_unauthorized_oauth_cannot_open_producer(self):
        from types import SimpleNamespace
        args=SimpleNamespace(rclone_config="/absent")
        with patch.object(m.os,"geteuid",return_value=1001), \
             patch.object(m,"_validate_owner_oauth_config",side_effect=m.TransferHold("FIXTURE_HOLD")), \
             patch.object(m,"VerifiedCompressedSource",side_effect=AssertionError("SOURCE_MUST_NOT_OPEN")):
            with self.assertRaisesRegex(m.TransferHold,"FIXTURE_HOLD"):
                m.run(args)
