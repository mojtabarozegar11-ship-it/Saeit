"""Native store integration for real independent, private shard proof."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tarfile
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]/"scripts"
def read_mod(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/file)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
shards=read_mod("shards","factory_zip_transport_shards_20261020.py")
transport=read_mod("transport","factory_private_shard_receiver_20261020.py")
native=read_mod("native","zomorod_factory_store_import.py")

class NativeStoreShards(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.home=Path(tmp.name);self.root=self.home/"factory";self.root.mkdir()
        for recipe in sorted(shards.RECIPES):
            source=self.root/"digital-products"/recipe
            source.mkdir(parents=True)
            package=source/(recipe+"-internal-qa.zip")
            with zipfile.ZipFile(package,"w") as z:
                for i in range(97):z.writestr(recipe+f"/component{i:03d}.txt",f"real {recipe} {i}")
            (source/"manufacturing_manifest.json").write_text(json.dumps({
                "recipe":recipe,"qa_status":"passed",
                "source_sha256":"a"*64,"artifact_sha256":shards.filehash(package),
                "owner_publication_approval":False,"public_listing_enabled":False}))
        shards.cycle(self.root)
        archive=self.home/"private.tar.gz"
        with tarfile.open(archive,"w:gz") as z:
            z.add(self.root/"product-lifecycle/private-transport-shards",arcname="private-transport-shards")
        self.stage=self.home/"dest"
        batch=transport.receive(archive,self.stage)
        self.batch=self.stage/batch["encrypted_transport_archive_sha256"]
        self.db=self.home/"site_store.sqlite3"
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE TABLE products(id INTEGER)")
            db.execute("CREATE TABLE payment_state(id INTEGER)")
        self.verifier=ROOT/"factory_private_shard_receiver_20261020.py"
    def test_five_real_private_goods_registered_without_any_approval(self):
        first=native.import_verified_private_shards(self.batch,self.db,self.verifier)
        self.assertEqual(first["new_private_store_candidates"],5)
        self.assertEqual(first["verified_parts"],10)
        self.assertEqual(first["source_files_verified"],485)
        self.assertEqual(first["owner_release_approvals"],0)
        self.assertEqual(first["publications"],0)
        replay=native.import_verified_private_shards(self.batch,self.db,self.verifier)
        self.assertEqual(replay["new_private_store_candidates"],0)
        self.assertEqual(replay["previously_staged"],5)
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM factory_private_shard_candidates").fetchone()[0],5)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM factory_shard_evidence_queue").fetchone()[0],5)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM products").fetchone()[0],0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM payment_state").fetchone()[0],0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM factory_private_shard_candidates WHERE public_enabled=1").fetchone()[0],0)
    def test_fake_owner_approval_or_corrupt_shard_fails_closed(self):
        receipt=self.batch/"verification.json"
        obj=json.loads(receipt.read_text());obj["owner_publication_approval"]=True
        receipt.write_text(json.dumps(obj))
        with self.assertRaisesRegex(ValueError,"PRIVATE_SHARD_BATCH_RECEIPT_MISMATCH"):
            native.import_verified_private_shards(self.batch,self.db,self.verifier)
        with sqlite3.connect(self.db) as db:
            self.assertFalse(db.execute("SELECT name FROM sqlite_master WHERE name='factory_private_shard_candidates'").fetchone())
    def test_other_store_schema_refused(self):
        with sqlite3.connect(self.db) as db: db.execute("DROP TABLE payment_state")
        with self.assertRaisesRegex(ValueError,"NOT_NATIVE_ZOMOROD_STORE_DATABASE"):
            native.import_verified_private_shards(self.batch,self.db,self.verifier)

if __name__=="__main__":
    unittest.main()
