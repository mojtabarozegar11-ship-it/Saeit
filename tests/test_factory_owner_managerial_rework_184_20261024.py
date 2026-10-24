"""Executable tests for the signed-off 184-artifact rework order."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[1]/"scripts/factory_owner_managerial_rework_184_20261024.py"
spec = importlib.util.spec_from_file_location("owner_rework", SCRIPT)
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class ManagerialReworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/"factory-private"
        self.area = self.root/"production-instructions"
        for item in (p.RECEIPTS, p.MANIFESTS, "stage-05/archives"):
            (self.area/item).mkdir(parents=True, mode=0o700)
        self.names = [f"WO-{i:08d}--r001.json" for i in (1, 2)]
        self.populate()

    def populate(self):
        repeated = ("A distinct research task requires primary data, source page, "
                    "local conditions, independent evidence, and uncertainty "
                    "before field application can be justified.\n\n")*12
        for name in self.names:
            prefix = "agri-"+name[:-5]+"/"
            manuscript = repeated.encode()
            files = {"README.md":b"private", "index.html":b"<html>test</html>",
                     "fa-IR.md":manuscript, "en-US.md":manuscript,
                     "sources.json":b"[]", "integrity.json":b"{}"}
            archive = self.area/"stage-05/archives"/(name[:-5]+".zip")
            with zipfile.ZipFile(archive,"w") as z:
                for key, value in files.items():
                    z.writestr(prefix+key, value)
            raw = archive.read_bytes()
            digest = hashlib.sha256
            (self.area/p.RECEIPTS/name).write_text(json.dumps({
                "order_id":name.split("--r")[0],
                "scientific_quality_certified":False,
                "ready_for_paid_store":False,
                "public_distribution_allowed":False,
                "archive_relative_path":str(archive.relative_to(self.area)),
                "zip_bytes":len(raw),"zip_sha256":digest(raw).hexdigest()}))
            (self.area/p.MANIFESTS/name).write_text(json.dumps({
                "order_id":name.split("--r")[0], "revision":1,
                "draft_kind":"original_bilingual_evidence_method_workbook",
                "manuscript_sha256":{k:digest(manuscript).hexdigest()
                                    for k in ("fa-IR","en-US")}}))

    def test_exact_scope_and_immutable_idempotent_receipts(self):
        self.assertEqual(p.execute(self.root,2,write=False)["validated"],2)
        one=p.execute(self.root,2)
        self.assertEqual(one["new_tickets"],2)
        self.assertEqual(one["held_from_publication"],2)
        self.assertEqual(p.execute(self.root,2)["new_tickets"],0)
        for name in self.names:
            obj=json.loads((self.area/p.REWORK/name).read_text())
            self.assertEqual(obj["disposition"],"RETURN_TO_STAGE5_SUBSTANTIVE_REWORK")
            self.assertFalse(obj["quality1000_approved"])
            self.assertEqual(obj["original_archive_sha256"],
                             json.loads((self.area/p.RECEIPTS/name).read_text())["zip_sha256"])

    def test_partial_or_wrong_inventory_will_not_mutate(self):
        with self.assertRaisesRegex(RuntimeError,"MEASURED_ARTIFACT_COUNT_CHANGED"):
            p.execute(self.root)
        self.assertFalse((self.area/p.REWORK).exists())

    def test_tampered_archive_prevents_all_tickets(self):
        folder=self.area/"stage-05/archives"
        archive=folder/(self.names[1][:-5]+".zip")
        archive.write_bytes(archive.read_bytes()+b"modified")
        with self.assertRaisesRegex(RuntimeError,"ARCHIVE_SHA_OR_SIZE_MISMATCH"):
            p.execute(self.root,2)
        self.assertFalse((self.area/p.REWORK).exists())

    def test_unrelated_preexisting_return_file_is_preserved_and_blocks(self):
        target=self.area/p.REWORK
        target.mkdir()
        (target/"not-owned.txt").write_text("valuable")
        with self.assertRaisesRegex(RuntimeError,"FOREIGN_REWORK_TICKETS"):
            p.execute(self.root,2)
        self.assertEqual((target/"not-owned.txt").read_text(),"valuable")

    def test_rejects_fabricated_qc_approval(self):
        name=self.names[0]
        receipt=self.area/p.RECEIPTS/name
        doc=json.loads(receipt.read_text())
        doc["quality1000_approved"]=True
        receipt.write_text(json.dumps(doc))
        with self.assertRaisesRegex(RuntimeError,"EXISTING_RELEASE_CONFLICT"):
            p.execute(self.root,2)
        self.assertFalse((self.area/p.REWORK).exists())


if __name__=="__main__":
    unittest.main()
