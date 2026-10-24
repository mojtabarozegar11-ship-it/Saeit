"""Real licensed bytes, no automatic claim substitution and all-order coverage."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,str(path))
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

m=load(ROOT/"scripts/factory_qc184_licensed_replacement_discovery_20261024.py","alternatives")
p=load(ROOT/"scripts/factory_primary_fulltext_acquisition_20261024.py","primary_for_alternatives")
PRIMARY=ROOT/"scripts/factory_primary_fulltext_acquisition_20261024.py"

def xml(doi, license_url="https://creativecommons.org/licenses/by/4.0/"):
    paras="".join("<p>"+("Wheat irrigation monitoring measured soil moisture and field response with randomized methods. "*20)+"</p>" for _ in range(3))
    return ('<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>'
            '<article-id pub-id-type="doi">'+doi+'</article-id>'
            '<permissions><license xlink:href="'+license_url+'">Creative Commons</license></permissions>'
            '</article-meta></front><body><sec>'+paras+'</sec></body></article>').encode()

def build(root,n=2):
    area=root/"production-instructions"
    inbox=area/"stage-02/primary-fulltext-repair-inbox"
    inbox.mkdir(parents=True)
    for i in range(n):
        name=f"WO-{i+1:08d}--r001.json"
        tasks=[{"source_id":f"S{k}","doi":f"10.1000/original-{k}",
                "title":"Wheat irrigation soil moisture monitoring field response",
                "original_fulltext_retrieved":False,
                "exact_supporting_pages_verified":False,
                "required_action":"FETCH_LICENSABLE_PRIMARY_FULLTEXT_AND_CHECK_EXACT_PASSAGES",
                "linked_claim_ids":["C1"]} for k in range(4)]
        claims=[{"claim_id":f"C{k}","indexed_abstract_statement":
                 "Wheat soil moisture response and irrigation observations require full text.",
                 "source_ids":["S0"]} for k in range(1,6)]
        (inbox/name).write_text(json.dumps({
            "schema":"saeit.factory.scientific-source-repair.v1",
            "order_file":name,"scientific_primary_source_tasks":tasks,
            "scientific_claims":claims,"all_claims_verified":False,
            "qc1000_approved":False,"public_distribution_allowed":False}))
    target=area/"stage-02/primary-source-acquisition-v1"
    for k,state in enumerate(("DOI_NOT_INDEXED_AT_EUROPE_PMC",
                              "NO_PMC_FULLTEXT_LINK",
                              "COMMERCIAL_REUSE_LICENSE_NOT_VERIFIED",
                              "RETRACTION_FLAGGED")):
        doi=f"10.1000/original-{k}"
        p.once(target/"metadata"/(p.key(doi)+".json"),p.canonical({
            "schema":p.SCHEMA,"doi":doi,"state":state,
            "qc1000_approved":False,"public_distribution_allowed":False}))
    return inbox

def provider(url, max_bytes):
    if "/search?" in url:
        return json.dumps({"resultList":{"result":[
            {"doi":"10.2000/alternative-1","pmcid":"PMC9876543",
             "title":"Wheat irrigation soil moisture monitoring under field conditions",
             "isRetracted":"N"},
            {"doi":"10.2000/alternative-2","pmcid":"PMC9876544",
             "title":"Wheat irrigation soil moisture monitoring for farms",
             "isRetracted":"N"}]}}).encode()
    if "PMC9876543" in url:
        return xml("10.2000/alternative-1")
    if "PMC9876544" in url:
        return xml("10.2000/alternative-2",
                   "https://creativecommons.org/licenses/by-nc/4.0/")
    raise AssertionError(url)

class AlternativeTests(unittest.TestCase):
    def test_private_coverage_and_licensed_xml_only(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            inbox=build(root)
            original=(inbox/"WO-00000001--r001.json").read_bytes()
            dry=m.execute(root,PRIMARY,dry_run=True)
            self.assertEqual((dry["orders"],dry["eligible_unusable_dois"]),(2,3))
            self.assertEqual(dry["network_attempts"],0)
            result=m.execute(root,PRIMARY,batch=2,http_get=provider)
            self.assertEqual(result["licensed_alternatives_found"],2)
            self.assertEqual(result["reports_total"],2)
            evidence=root/"production-instructions/stage-02/licensed-alternative-discovery-v1"
            xmls=list((evidence/"licensed-xml").glob("*.xml"))
            self.assertEqual(len(xmls),1)
            self.assertEqual(p.sha(xmls[0].read_bytes()),
                             p.sha(xml("10.2000/alternative-1")))
            report=json.loads(next((evidence/"reports").glob("*.json")).read_text())
            self.assertFalse(report["qc1000_approved"])
            self.assertFalse(report["candidates"][0]["claim_support_verified"])
            self.assertFalse(report["candidates"][0]["source_substitution_approved"])
            self.assertTrue(report["independent_reviewer_required"])
            self.assertEqual(original,(inbox/"WO-00000001--r001.json").read_bytes())
            another=m.execute(root,PRIMARY,batch=2,http_get=provider)
            self.assertEqual(another["reports_total"],3)
            self.assertEqual(len(list((evidence/"licensed-xml").glob("*.xml"))),1)

    def test_broken_provider_does_not_approve_or_poison_retry(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            build(root)
            def error(url,limit):
                raise OSError("SOURCE_HTTP_500")
            result=m.execute(root,PRIMARY,batch=3,http_get=error)
            self.assertEqual(result["transient_retry_pending"],3)
            self.assertEqual(result["reports_total"],0)
            result=m.execute(root,PRIMARY,batch=3,http_get=provider)
            self.assertEqual(result["reports_total"],3)
            self.assertEqual(result["scientific_approvals_created"],0)

    def test_title_query_is_sanitized_and_short_title_blocked(self):
        self.assertIsNone(m.candidate_search_query("Test 2"))
        query=m.candidate_search_query("Wheat; DROP TABLE irrigation soil")
        self.assertNotIn(";",query)
        self.assertNotIn("DROP TABLE",query)
        self.assertIn("OPEN_ACCESS:y",query)

if __name__=="__main__":
    unittest.main()
