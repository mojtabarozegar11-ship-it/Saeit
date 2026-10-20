"""Check private cPanel archive reception for five unchanged sharded collections."""
import importlib.util
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]/"scripts"
def get(name,filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/filename)
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

sender=get("shards","factory_zip_transport_shards_20261020.py")
receiver=get("receiver","factory_private_shard_receiver_20261020.py")

class ReceivePrivateShards(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.home=Path(t.name)
        self.factory=self.home/"factory"
        self.factory.mkdir()
        for recipe in sender.RECIPES:
            p=self.factory/"digital-products"/recipe
            p.mkdir(parents=True)
            archive=p/(recipe+"-internal-qa.zip")
            with zipfile.ZipFile(archive,"w") as z:
                for i in range(97):
                    z.writestr(recipe+"/item%03d.txt"%i,"authentic test %s /%d"%(recipe,i))
            (p/"manufacturing_manifest.json").write_text(json.dumps({
                "recipe":recipe,"qa_status":"passed","artifact_sha256":sender.filehash(archive),
                "source_sha256":"a"*64,"owner_publication_approval":False,
                "public_listing_enabled":False}))
        self.assertEqual(sender.cycle(self.factory)["products_verified"],5)
        self.tar=self.home/"all.tar.gz"
        with tarfile.open(self.tar,"w:gz") as archive:
            archive.add(self.factory/"product-lifecycle/private-transport-shards",
                        arcname="private-transport-shards")
        self.dest=self.home/"cpanel-private"
    def test_receive_verified_five_collections_twice(self):
        result=receiver.receive(self.tar,self.dest)
        self.assertEqual(result["products_verified"],5)
        self.assertEqual(result["shards_verified"],10)
        self.assertEqual(result["files_reconstructed"],485)
        self.assertFalse(result["publicly_published"])
        self.assertFalse(result["customer_payment_created"])
        self.assertTrue(result["private_reconstruction_passed"])
        self.assertEqual(receiver.receive(self.tar,self.dest),result)
    def test_detect_changed_transferred_part(self):
        result=receiver.receive(self.tar,self.dest)
        batch=self.dest/result["encrypted_transport_archive_sha256"]
        folder=batch/"private-transport-shards"/sender.RECIPES[0]
        version=next(folder.iterdir())
        (version/"part-001.zip").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError,"CPANEL_PART_DIGEST_MISMATCH"):
            receiver.receive(self.tar,self.dest)
    def test_reject_tar_file_path_traversal(self):
        import io
        with tarfile.open(self.tar,"w:gz") as z:
            info=tarfile.TarInfo("private-transport-shards/../../other")
            info.size=5
            z.addfile(info,io.BytesIO(b"hello"))
        with self.assertRaisesRegex(ValueError,"CPANEL_TAR_MEMBER_UNSAFE"):
            receiver.receive(self.tar,self.dest)
        self.assertFalse(list(self.dest.glob("*/verification.json")))

if __name__=="__main__":
    unittest.main()
