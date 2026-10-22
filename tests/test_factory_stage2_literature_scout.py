"""No-network proof of Stage 2 real-abstract discovery and honest fail-closed gates."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

BASE=Path(__file__).resolve().parents[1]
def module(name,file):
    spec=importlib.util.spec_from_file_location(name,BASE/"scripts"/file)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

SCOUT=module("factory_stage2_scout","factory_stage2_literature_scout.py")
STAGE2=module("factory_stage2_core_scout","factory_stage2_research.py")
STAGE1=module("factory_stage1_scout","factory_stage1_handoff.py")
AGRI=module("factory_agri_scout","factory_agri200_p0_intake.py")
CATALOG=BASE/"docs/agri200_p0_catalog.tsv"


def indexed(words):
    mapping={}
    for n,word in enumerate(words.split()):
        mapping.setdefault(word,[]).append(n)
    return mapping


def study(query,n):
    topic_words=[w for w in SCOUT.keys(query)]
    if not topic_words:
        topic_words=["houseplant","watering"]
    phrase=" ".join(topic_words)
    sentence=(
        "A systematic study of "+phrase+" identified measurable differences "
        "in substrate, growing conditions, and plant outcomes under "
        "contrasting controlled agricultural treatments."
    )
    abstract=(
        sentence+" We recorded environmental conditions and physiological "
        "characteristics of treated ornamental crops during repeated sampling. "
        "The investigators examined test groups using measured observations, "
        "statistical comparisons, and repeatable field procedures in multiple "
        "agricultural environments. Additional experiments are required to "
        "evaluate applicability to new climate regions or production systems."
    )
    return {
        "id":"https://openalex.org/W"+str(900000000+n),
        "display_name":"Research on "+phrase+" in controlled horticultural production systems",
        "doi":"https://doi.org/10.5500/research."+str(n),
        "publication_year":2020+n,
        "type":"article","is_retracted":False,
        "primary_location":{
            "landing_page_url":"https://scientificpublisher"+str(n)+".org/article",
            "source":{"host_organization_name":"Scientific Publisher "+str(n),
                      "display_name":"Applied Horticulture Journal "+str(n)}},
        "abstract_inverted_index":indexed(abstract)
    }


def sample(query):
    return [study(query,n) for n in range(1,7)]


class SourceScoutTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        AGRI.install(self.root,CATALOG)
        STAGE1.run(self.root,batch=200)
        self.area=self.root/"production-instructions"
        self.program=BASE/"scripts/factory_stage2_research.py"

    def order(self,rank):
        index=STAGE2.read(self.area/"owner-agri200-p0-index.json")
        order_id=index["order_ids_ranked"][rank-1]
        return STAGE2.verified_stage1_packet(self.area,order_id+"--r001.json")[1]

    def test_short_sentence_reconstructed_exactly_from_index(self):
        paper=study("Houseplant Rescue Guide",1)
        abstract=SCOUT.abstract_from_index(paper["abstract_inverted_index"])
        candidate=SCOUT.citation_sentence(abstract,SCOUT.keys("Houseplant Rescue Guide"))
        self.assertIsNotNone(candidate)
        self.assertIn(candidate,abstract)
        self.assertLessEqual(len(candidate.split()),24)

    def test_realistic_indexed_abstracts_can_finish_only_desk_research(self):
        count=SCOUT.run(self.root,self.program,
                        fetcher=sample,backstop=lambda title:[],
                        batch=1,workers=1)
        self.assertEqual(count["source_evidence_automatically_documented"],1)
        evidence=STAGE2.read(self.area/"stage-02/source-evidence/AGRI-001--r001.json")
        self.assertEqual(len(evidence["sources"]),5)
        self.assertFalse(evidence["independent_original_page_recheck"])
        self.assertTrue(all(x["statement"] in SCOUT.abstract_from_index(
                sample("Houseplant Rescue Guide")[n]["abstract_inverted_index"])
            for n,x in enumerate(evidence["claims"])))
        self.assertEqual(STAGE2.stage2_loop(self.root,batch=1)[
            "newly_completed_research_dossiers"],1)
        packet=STAGE2.read(self.area/"stage-03/inbox/WO-00000001--r001.json")
        self.assertFalse(packet["independent_expert_review"])
        self.assertFalse(packet["quality1000_approved"])
        self.assertFalse(packet["public_distribution_allowed"])

    def test_unrelated_papers_cannot_be_promoted(self):
        def unrelated(title):
            return sample("unrelated hydroelectric turbine mechanics")
        got=SCOUT.run(self.root,self.program,fetcher=unrelated,
                      backstop=lambda title:[],batch=1,workers=1)
        self.assertEqual(got["source_evidence_automatically_documented"],0)
        self.assertEqual(got["still_require_manual_or_external_research"],1)
        self.assertFalse((self.area/"stage-02/source-evidence/AGRI-001--r001.json").exists())
        self.assertTrue((self.area/"stage-02/literature-candidates/AGRI-001--r001.json").is_file())

    def test_publisher_diversity_and_no_retracted_papers(self):
        title="Houseplant Rescue Guide"
        papers=sample(title)
        for p in papers:
            p["primary_location"]["landing_page_url"]="https://same.publisher.org/story"
            p["primary_location"]["source"]["host_organization_name"]="Same Publisher"
        chosen=SCOUT.select_papers(papers,SCOUT.keys(title),STAGE2)
        self.assertEqual(len(chosen),6)
        self.assertIsNone(SCOUT.evidence_from_papers(self.order(1),1,chosen,STAGE2))
        paper=study(title,7)
        paper["is_retracted"]=True
        self.assertIsNone(SCOUT.usable_paper(paper,SCOUT.keys(title),STAGE2))

    def test_unavailable_provider_does_not_fake_source(self):
        def down(_):
            raise TimeoutError("provider offline")
        got=SCOUT.run(self.root,self.program,fetcher=down,
                      backstop=lambda _:[],batch=1,workers=1)
        self.assertEqual(got["external_provider_unavailable"],1)
        self.assertFalse((self.area/"stage-02/source-evidence/AGRI-001--r001.json").exists())

    def test_safety_sensitive_topic_remains_research_only(self):
        order=self.order(1)
        order["subject"]="Mushroom pesticide toxicity research"
        papers=SCOUT.select_papers(sample("Houseplant Rescue Guide"),
                                  SCOUT.keys("Houseplant Rescue Guide"),STAGE2)
        self.assertIsNone(SCOUT.evidence_from_papers(order,1,papers,STAGE2))

    def test_idempotent_provider_cache_keeps_original_sources(self):
        got=SCOUT.run(self.root,self.program,fetcher=sample,
                      backstop=lambda _:[],batch=1,workers=1)
        self.assertEqual(got["source_evidence_automatically_documented"],1)
        path=self.area/"stage-02/source-evidence/AGRI-001--r001.json"
        before=path.read_bytes()
        again=SCOUT.run(self.root,self.program,fetcher=sample,
                        backstop=lambda _:[],batch=1,workers=1)
        self.assertEqual(again["source_evidence_automatically_documented"],1)
        self.assertEqual(path.read_bytes(),before)


if __name__=="__main__":
    unittest.main()
