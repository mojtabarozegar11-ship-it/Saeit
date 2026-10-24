"""184-order, evidence-reuse, source-license and QC1000 fail-closed tests."""
from pathlib import Path
import importlib.util
import json
import tempfile
import unittest
from urllib.parse import unquote

SRC = Path(__file__).resolve().parents[1]/"scripts/factory_primary_fulltext_acquisition_20261024.py"
spec = importlib.util.spec_from_file_location("primary_source_acquisition",SRC)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def article(doi, license_url="https://creativecommons.org/licenses/by/4.0/"):
    paragraphs = "".join("<p>"+("Farming evidence and irrigation monitoring from peer reviewed agricultural experiments supports controlled field observations. "*12)+"</p>" for _ in range(3))
    return ('<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>'
            '<article-id pub-id-type="doi">'+doi+'</article-id><permissions><license xlink:href="'
            +license_url+'">Creative Commons</license></permissions></article-meta></front>'
            '<body><sec><title>Study findings</title>'+paragraphs+'</sec></body></article>').encode()

def build(root, n=184):
    inbox=root/"production-instructions"/"stage-02/primary-fulltext-repair-inbox"
    inbox.mkdir(parents=True)
    for i in range(1,n+1):
        name="WO-%08d--r001.json"%i
        tasks=[{"source_id":"S%d"%k,"doi":"10.1000/realstudy-%d"%k,
                "required_action":"FETCH_LICENSABLE_PRIMARY_FULLTEXT_AND_CHECK_EXACT_PASSAGES",
                "original_fulltext_retrieved":False,"exact_supporting_pages_verified":False,
                "linked_claim_ids":["C%d"%(k+1)]} for k in range(4)]
        claims=[{"claim_id":"C%d"%k,"indexed_abstract_statement":
                 "Farming irrigation and evidence monitoring support controlled agricultural experimental observations in the field.",
                 "source_ids":["S%d"%((k-1)%4)]} for k in range(1,6)]
        pkt={"schema":"saeit.factory.scientific-source-repair.v1",
             "order_file":name,"scientific_primary_source_tasks":tasks,
             "scientific_claims":claims,"all_claims_verified":False,
             "qc1000_approved":False,"public_distribution_allowed":False}
        (inbox/name).write_text(json.dumps(pkt),encoding="utf8")

def simulated(url, limit):
    if "/search?" in url:
        doi=unquote(url.split("DOI%3A%22")[1].split("%22")[0]).lower()
        pmcid="PMC123456"+doi[-1]
        return json.dumps({"resultList":{"result":[{
            "doi":doi,"pmcid":pmcid,"isRetracted":"N"}]}}).encode()
    if "fullTextXML" in url:
        return article("10.1000/realstudy-"+url.split("PMC123456")[1][0])
    raise AssertionError(url)

class PrimarySourceTests(unittest.TestCase):
    def test_all_184_deduplicated_real_source_bytes_and_private_claim_maps(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            build(root)
            original=(root/"production-instructions/stage-02/primary-fulltext-repair-inbox/WO-00000001--r001.json").read_bytes()
            dry=m.execute(root,dry_run=True)
            self.assertEqual(dry["orders"],184)
            self.assertEqual(dry["source_tasks"],736)
            self.assertEqual(dry["unique_dois"],4)
            self.assertFalse((root/"production-instructions/stage-02/primary-source-acquisition-v1").exists())
            results=m.execute(root,batch=20,http_get=simulated)
            self.assertEqual(results["LICENSED_FULLTEXT_ARCHIVED"],4)
            self.assertEqual(results["new_order_claim_candidate_maps"],184)
            self.assertEqual(results["qc1000_approvals"],0)
            self.assertEqual(results["publications"],0)
            retry=m.execute(root,http_get=lambda *_: (_ for _ in ()).throw(AssertionError("no duplicate HTTP")))
            self.assertEqual(retry["cached"],4)
            self.assertEqual(retry["new_order_claim_candidate_maps"],0)
            self.assertEqual(original,(root/"production-instructions/stage-02/primary-fulltext-repair-inbox/WO-00000001--r001.json").read_bytes())
            claim=json.loads((root/"production-instructions/stage-02/primary-source-acquisition-v1/claim-candidate-maps/WO-00000001--r001.json").read_text())
            self.assertFalse(claim["all_scientific_claims_verified"])
            self.assertFalse(claim["qc1000_approved"])
            self.assertEqual(len(claim["claims"]),5)
            self.assertTrue(claim["claims"][0]["reviewer_assistance_only"][0]["candidate_body_passages"])

    def test_commercially_restricted_license_produces_blocker_not_archived_xml(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            build(root,1)
            def restricted(url,limit):
                if "/search?" in url:
                    return simulated(url,limit)
                return article("10.1000/realstudy-"+url.split("PMC123456")[1][0],
                    "https://creativecommons.org/licenses/by-nc/4.0/")
            r=m.execute(root,batch=4,http_get=restricted)
            self.assertEqual(r["COMMERCIAL_REUSE_LICENSE_NOT_VERIFIED"],4)
            evidence=root/"production-instructions/stage-02/primary-source-acquisition-v1"
            self.assertEqual(len(list((evidence/"licensed-xml").glob("*.xml"))),0)
            report=json.loads((evidence/"claim-candidate-maps/WO-00000001--r001.json").read_text())
            self.assertEqual(report["licensed_source_count"],0)
            self.assertFalse(report["commercial_release"])

    def test_wrong_doi_or_forged_gate_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            build(root,1)
            def wrong_doi(url,limit):
                if "/search?" in url:
                    return simulated(url,limit)
                return article("10.1000/other-study")
            r=m.execute(root,batch=4,http_get=wrong_doi)
            self.assertEqual(r["FULLTEXT_REJECTED_FULLTEXT_DOI_MISMATCH"],4)
            packet=root/"production-instructions/stage-02/primary-fulltext-repair-inbox/WO-00000001--r001.json"
            q=json.loads(packet.read_text())
            q["qc1000_approved"]=True
            packet.write_text(json.dumps(q))
            with self.assertRaisesRegex(m.Blocked,"REWORK_PACKET_QC"):
                m.execute(root,dry_run=True)

    def test_transient_error_does_not_poison_future_fetch(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            build(root,1)
            r=m.execute(root,batch=4,http_get=lambda *_: (_ for _ in ()).throw(m.TemporaryFailure("429")))
            self.assertEqual(r["transient_retry_pending"],1)
            self.assertEqual(r["remaining_unique_dois"],4)
            r2=m.execute(root,batch=4,http_get=simulated)
            self.assertEqual(r2["LICENSED_FULLTEXT_ARCHIVED"],4)

    def test_one_transient_http_500_does_not_starve_remaining_sources(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            build(root,1)
            calls=[]
            def provider(url,limit):
                if "/search?" in url and "realstudy-0" in url:
                    calls.append("http500")
                    raise m.TemporaryFailure("SOURCE_HTTP_500")
                return simulated(url,limit)
            first=m.execute(root,batch=4,http_get=provider)
            self.assertEqual(first["transient_retry_pending"],1)
            self.assertEqual(first["LICENSED_FULLTEXT_ARCHIVED"],3)
            self.assertEqual(first["remaining_unique_dois"],1)
            self.assertFalse(first["qc1000_approvals"])
            retry=m.execute(root,batch=4,http_get=simulated)
            self.assertEqual(retry["LICENSED_FULLTEXT_ARCHIVED"],1)
            self.assertEqual(retry["remaining_unique_dois"],0)
            self.assertEqual(retry["new_order_claim_candidate_maps"],1)

if __name__=="__main__":
    unittest.main()
