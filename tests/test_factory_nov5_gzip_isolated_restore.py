"""Independent offline encryption-to-gzip-to-SQLite fixture checks."""
import gzip
import hashlib
import io
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from scripts import factory_nov5_gzip_isolated_restore as m
from scripts.factory_dual_stream_v2 import encrypt_stream_to_dual_stores


class IsolatedHistoricalRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        key=rsa.generate_private_key(public_exponent=65537,key_size=3072,backend=default_backend())
        cls.pem=key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        pub=key.public_key()
        cls.pub=pub.public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        cls.spki=hashlib.sha256(pub.public_bytes(serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo)).hexdigest()

    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        home=Path(tmp.name).resolve()
        self.src=home/"encrypted"
        self.out=home/"isolated"
        self.src.mkdir(mode=0o700)
        self.out.mkdir(mode=0o700)
        db=home/"fixture.sqlite3"
        conn=sqlite3.connect(db)
        try:
            conn.execute("CREATE TABLE t (message TEXT)")
            conn.execute("INSERT INTO t VALUES ('private fixture')")
            conn.commit()
        finally:conn.close()
        self.raw=db.read_bytes()
        self.gz=gzip.compress(self.raw,mtime=0)
        self.a={};self.b={}
        receipt=encrypt_stream_to_dual_stores(io.BytesIO(self.gz),
            public_pem=self.pub,trusted_public_spki_sha256=self.spki,
            owner_a="fixture-a",owner_b="fixture-b",
            upload_a=lambda n,p:self.a.__setitem__(n,p),
            upload_b=lambda n,p:self.b.__setitem__(n,p),
            read_a=lambda n:self.a[n],read_b=lambda n:self.b[n],
            chunk_bytes=4096,max_source_bytes=len(self.gz))
        self.pin=receipt.manifest_sha256
        for name,payload in self.a.items():
            p=self.src/name;p.write_bytes(payload);p.chmod(0o600)
            if name.endswith("-manifest.json"):self.manifest=p
        self.assertEqual(self.a,self.b)
        self.enterContextCompat(patch.dict(m.direct.SOURCES,
            {"nov5-a":(len(self.gz),hashlib.sha256(self.gz).hexdigest())}))
        self.enterContextCompat(patch.dict(m.direct.legacy.SOURCES,
            {"nov5-a":("fixture.sqlite3",hashlib.sha256(self.raw).hexdigest())}))
        self.enterContextCompat(patch.object(m.direct.legacy,"SOURCE_BYTES",len(self.raw)))
        self.enterContextCompat(patch.object(m,"RESERVE",0))

    def enterContextCompat(self,ctx):
        ctx.__enter__()
        self.addCleanup(ctx.__exit__,None,None,None)

    def perform(self,**kw):
        return m.restore("nov5-a",self.manifest,kw.get("pin",self.pin),
            self.src,self.out,self.pem,None,expected_spki=kw.get("spki",self.spki))

    def test_actual_crypto_and_sqlite_roundtrip(self):
        result=self.perform()
        self.assertEqual(result["sqlite_integrity_check"],"ok")
        self.assertEqual((self.out/result["isolated_output"]).read_bytes(),self.raw)
        self.assertEqual(len(list(self.out.iterdir())),1)

    def test_destination_not_overwritten(self):
        result=self.perform()
        before=(self.out/result["isolated_output"]).read_bytes()
        with self.assertRaises(FileExistsError):self.perform()
        self.assertEqual((self.out/result["isolated_output"]).read_bytes(),before)
        self.assertEqual(len(list(self.out.iterdir())),1)

    def test_manifest_pin_mismatch(self):
        with self.assertRaises(ValueError):self.perform(pin="0"*64)
        self.assertEqual(list(self.out.iterdir()),[])

    def test_wrong_key_fingerprint(self):
        with self.assertRaises(ValueError):self.perform(spki="0"*64)
        self.assertEqual(list(self.out.iterdir()),[])

    def test_cipher_tamper_fails(self):
        part=next(p for p in self.src.iterdir() if p.suffix==".enc")
        data=part.read_bytes();part.write_bytes(data[:-1]+bytes([data[-1]^1]))
        with self.assertRaises(ValueError):self.perform()
        self.assertEqual(list(self.out.iterdir()),[])

    def test_wrong_raw_catalog_fails_after_authenticated_decrypt(self):
        with patch.dict(m.direct.legacy.SOURCES,{"nov5-a":("fixture","0"*64)}):
            with self.assertRaises(ValueError):self.perform()
        self.assertEqual(list(self.out.iterdir()),[])

    def test_public_ciphertext_permissions_denied(self):
        part=next(p for p in self.src.iterdir() if p.suffix==".enc")
        part.chmod(0o644)
        with self.assertRaises(ValueError):self.perform()
        self.assertEqual(list(self.out.iterdir()),[])

    def test_symlink_ciphertext_denied(self):
        part=next(p for p in self.src.iterdir() if p.suffix==".enc")
        target=part.with_suffix(".enc.original")
        part.rename(target);part.symlink_to(target)
        with self.assertRaises(ValueError):self.perform()
        self.assertEqual(list(self.out.iterdir()),[])
