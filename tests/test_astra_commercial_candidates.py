"""Safety and output tests for commercial product proposals, no real checkout."""
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase, main
import hashlib
import importlib.util
import json
import os
import sqlite3
import tempfile
import zipfile

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"astra_commercial_candidates.py"
spec=importlib.util.spec_from_file_location("astra_commercial_test",SCRIPT)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fixture(root):
    root=Path(root)
    conn=sqlite3.connect(str(root/"queue.sqlite3"))
    conn.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY,builder TEXT,artifact_sha TEXT,stage TEXT)")
    product_records=[]
    for idx,(builder,info) in enumerate(sorted(mod.CATALOG.items()),1):
        slug="product_"+str(idx)
        source_sha=hashlib.sha256(builder.encode()).hexdigest()
        artifact=root/("artifact-"+source_sha+".zip")
        names=["README.md","example.json","self_test.py"]
        with zipfile.ZipFile(artifact,"w",zipfile.ZIP_DEFLATED) as z:
            for name in names:
                z.writestr(slug+"/"+name,("test "+builder+" "+name).encode())
        zip_sha=mod.sha256_file(artifact)
        qa={
            "source_builder":builder,"artifact_sha256":zip_sha,
            "source_digest":source_sha,"product_slug":slug,
            "technical_regression":"PASSED","integrity_check":"PASSED",
            "development_scope":"private_reference_prototype",
            "commercial_product":False,"sale_ready":False,
            "public_deployment_allowed":False,"real_payment_allowed":False,
            "included_files":names,
        }
        (root/("qa-"+source_sha+".json")).write_text(json.dumps(qa))
        conn.execute("INSERT INTO jobs (builder,artifact_sha,stage) VALUES (?,?,?)",
                     (builder,zip_sha,"PRIVATE_QA_PASSED"))
        product_records.append((builder,source_sha,zip_sha))
    conn.commit()
    conn.close()
    return product_records


class PrivateCommercializationTests(TestCase):
    def test_four_checksum_verified_candidates_all_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d)
            report=mod.private_catalog(d,now=datetime(2026,10,15,tzinfo=timezone.utc))
            self.assertEqual(len(report["items"]),4)
            self.assertEqual(report["publications"],0)
            self.assertEqual(report["real_checkout_transactions"],0)
            self.assertFalse(report["real_payment_engine_live_verified"])
            self.assertEqual([x["suggested_discount_percent"] for x in report["items"]],[90]*4)
            for p in report["items"]:
                self.assertIsNone(p["quality_score"])
                self.assertFalse(p["checkout_authorized"])
                self.assertFalse(p["rights_verified"])
                self.assertFalse(p["public_listing_authorized"])
                self.assertEqual(len(p["source_proof"]["artifact_sha256"]),64)
            self.assertEqual({p["sku"]:p["suggested_discounted_price_usd"]
                              for p in report["items"]},{
               "ASTRA-ORCHARD-01":"1.90","ASTRA-PROCURE-01":"1.90",
               "ASTRA-WATER-01":"2.90","ASTRA-CIRCUIT-01":"0.50"})

    def test_immutable_private_catalog_does_not_rewrite(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"source"
            src.mkdir()
            fixture(src)
            target=Path(d)/"private-proposals"
            first=mod.store_private_catalog(mod.private_catalog(src),target)
            self.assertEqual(first["status"],"PRIVATE_CANDIDATE_CREATED")
            saved=target/first["name"]
            original=saved.read_bytes()
            self.assertEqual(saved.stat().st_mode & 0o777,0o600)
            second=mod.store_private_catalog(mod.private_catalog(src),target)
            self.assertEqual(second["status"],"UNCHANGED")
            self.assertEqual(original,saved.read_bytes())
            self.assertEqual(len(list(target.glob("commercial-catalog-*.json"))),1)

    def test_tampered_zip_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            records=fixture(d)
            _,source,_=records[0]
            archive=Path(d)/("artifact-"+source+".zip")
            with archive.open("ab") as f:
                f.write(b"tamper")
            with self.assertRaisesRegex(ValueError,"digest mismatch"):
                mod.private_catalog(d)

    def test_fake_market_ready_flag_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            records=fixture(d)
            _,source,_=records[0]
            qa=Path(d)/("qa-"+source+".json")
            data=json.loads(qa.read_text())
            data["sale_ready"]=True
            qa.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"private QA gates"):
                mod.private_catalog(d)

    def test_missing_builder_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            records=fixture(d)
            conn=sqlite3.connect(str(Path(d)/"queue.sqlite3"))
            conn.execute("DELETE FROM jobs WHERE builder=?",(records[0][0],))
            conn.commit()
            conn.close()
            with self.assertRaisesRegex(ValueError,"not all four"):
                mod.private_catalog(d)

    def test_symlink_zip_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            records=fixture(d)
            _,source,_=records[0]
            zipfile_path=Path(d)/("artifact-"+source+".zip")
            target=Path(d)/"external.zip"
            zipfile_path.rename(target)
            zipfile_path.symlink_to(target)
            with self.assertRaisesRegex(ValueError,"artifact missing/unsafe"):
                mod.private_catalog(d)

    def test_reject_no_private_queue(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,"verified private queue"):
                mod.private_catalog(d)

    def test_reject_unsafe_root_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d)
            link=Path(d).parent/(Path(d).name+"-ref")
            try:
                link.symlink_to(d)
                with self.assertRaisesRegex(ValueError,"symlink"):
                    mod.private_catalog(link)
            finally:
                link.unlink(missing_ok=True)

    def test_no_payment_network_or_publication_modules_imported(self):
        raw=SCRIPT.read_text()
        for token in ("import requests", "import django", "urllib.request",
                      "subprocess.run", "PaymentIntent", "ALTER TABLE", "INSERT INTO"):
            self.assertNotIn(token,raw)


if __name__=="__main__":
    main()
