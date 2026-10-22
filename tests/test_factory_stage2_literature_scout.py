"""No-network proof of Stage 2 real-abstract discovery and honest fail-closed gates."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import datetime as dt
import time
import urllib.error
from unittest import mock

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


    def test_http429_switches_on_short_shared_provider_circuit_breaker(self):
        endpoint=SCOUT.SAFE_KEYS["openalex"]
        class BlockedOpener:
            def open(self,request,timeout=None):
                raise urllib.error.HTTPError(
                    request.full_url,429,"rate limit",{"Retry-After":"120"},None)
        SCOUT.PROVIDER_NEXT_ALLOWED.clear()
        try:
            with mock.patch.object(SCOUT.urllib.request,"build_opener",
                                   return_value=BlockedOpener()):
                with self.assertRaisesRegex(RuntimeError,"SCOUT_API_RATE_LIMITED_429"):
                    SCOUT.request_json(endpoint,{"search":"houseplants"})
            self.assertGreater(SCOUT.PROVIDER_NEXT_ALLOWED[endpoint],
                               time.monotonic()+100)
            with mock.patch.object(SCOUT.urllib.request,"build_opener",
                                   side_effect=AssertionError("must not call provider")):
                with self.assertRaises(SCOUT.ProviderCoolingDown):
                    SCOUT.request_json(endpoint,{"search":"indoor foliage"})
        finally:
            SCOUT.PROVIDER_NEXT_ALLOWED.clear()

    def test_provider_cooldown_does_not_create_false_scientific_gap(self):
        def cooling(_):
            raise SCOUT.ProviderCoolingDown("SCOUT_PROVIDER_COOLING_DOWN")
        result=SCOUT.run(self.root,self.program,fetcher=cooling,
                         backstop=lambda _:[],batch=1,workers=1)
        self.assertEqual(result["requests_skipped_due_to_provider_cooldown"],1)
        self.assertEqual(result["still_require_manual_or_external_research"],0)
        self.assertFalse((self.area/"stage-02/literature-candidates/AGRI-001--r001.json").exists())

    def test_rate_limited_attempt_retries_after_minutes_not_18_hours(self):
        import datetime as dt
        index=STAGE2.read(self.area/"owner-agri200-p0-index.json")
        # Keep all other P0 inputs newly blocked with recent provider failures,
        # so rank 1's 13-minute-old failure becomes the next eligible retry.
        now=dt.datetime.now(dt.timezone.utc)
        for n in range(1,201):
            checked=(now-dt.timedelta(minutes=13) if n==1 else now)
            candidate={
                "schema":SCOUT.SCHEMA,"source_product_id":"AGRI-%03d"%n,
                "order_id":index["order_ids_ranked"][n-1],
                "status":"external_research_api_unavailable",
                "checked_utc":checked.isoformat(),
                "commercial_release":False
            }
            STAGE2.atomic(self.area/"stage-02/literature-candidates"/
                          ("AGRI-%03d"%n+"--r001.json"),candidate)
        queries=[]
        def stub(title):
            queries.append(title)
            return sample(title)
        result=SCOUT.run(self.root,self.program,fetcher=stub,
                         backstop=lambda _:[],batch=1,workers=1)
        self.assertEqual(result["source_evidence_automatically_documented"],1)
        self.assertEqual(queries,["Houseplant Rescue Guide"])
        self.assertTrue((self.area/"stage-02/source-evidence/AGRI-001--r001.json").exists())

    def test_unsearched_ranked_work_is_not_starved_by_retried_errors(self):
        # rank 1's error is old; rank 2 has never been searched.
        old=dt.datetime.now(dt.timezone.utc)-dt.timedelta(hours=1)
        index=STAGE2.read(self.area/"owner-agri200-p0-index.json")
        STAGE2.atomic(self.area/"stage-02/literature-candidates/AGRI-001--r001.json",{
            "schema":SCOUT.SCHEMA,"source_product_id":"AGRI-001",
            "order_id":index["order_ids_ranked"][0],
            "status":"external_research_api_unavailable",
            "checked_utc":old.isoformat(),
            "commercial_release":False
        })
        requested=[]
        def stub(title):
            requested.append(title)
            return []
        SCOUT.run(self.root,self.program,fetcher=stub,
                  backstop=lambda _:[],batch=1,workers=1)
        self.assertEqual(requested,["Diagnose Yellow Plant Leaves"])

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



    def test_private_api_key_is_sent_as_header_and_never_reported(self):
        import os
        endpoint=SCOUT.SAFE_KEYS["openalex"]
        secret="OpenAlexTestKey_123456789012345"
        seen=[]
        class GoodResponse:
            status=200
            headers={}
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def read(self,n): return b'{"results":[]}'
        class GoodOpener:
            def open(self,request,timeout=None):
                seen.append(request.get_header("Authorization"))
                return GoodResponse()
        SCOUT.PROVIDER_NEXT_ALLOWED.clear()
        with mock.patch.dict(os.environ,{"OPENALEX_API_KEY":secret}):
            with mock.patch.object(SCOUT.urllib.request,"build_opener",
                                   return_value=GoodOpener()):
                result=SCOUT.request_json(endpoint,{"search":"soil"})
        self.assertEqual(result["results"],[])
        self.assertEqual(seen,["Bearer "+secret])
        self.assertNotIn(secret,json.dumps(result))

    def test_provider_cooldown_persists_across_process_runs(self):
        endpoint=SCOUT.SAFE_KEYS["openalex"]
        path=self.area/"stage-02/literature-provider-cooldowns.json"
        tomorrow=(dt.datetime.now(dt.timezone.utc)+
                  dt.timedelta(minutes=5)).isoformat()
        STAGE2.atomic(path,{
            "schema":"saeit.factory.provider-cooldown.v1",
            "blocked_until_utc":{endpoint:tomorrow},
            "checked_utc":SCOUT.utc()})
        SCOUT.PROVIDER_NEXT_ALLOWED.clear()
        def attempt(_):
            SCOUT.request_json(endpoint,{"search":"houseplants"})
            return []
        with mock.patch.object(SCOUT.urllib.request,"build_opener",
                               side_effect=AssertionError("no remote call during cooldown")):
            got=SCOUT.run(self.root,self.program,fetcher=attempt,
                          backstop=lambda _:[],batch=1,workers=1)
        self.assertEqual(got["requests_skipped_due_to_provider_cooldown"],1)
        self.assertTrue(got["provider_cooldown_active"])
        saved=STAGE2.read(path)
        self.assertIn(endpoint,saved["blocked_until_utc"])

    def test_new_private_key_invalidates_old_anonymous_quota_cooldown(self):
        import os
        endpoint=SCOUT.SAFE_KEYS["openalex"]
        state=self.area/"stage-02/literature-provider-cooldowns.json"
        STAGE2.atomic(state,{
            "schema":"saeit.factory.provider-cooldown.v1",
            "blocked_until_utc":{endpoint:(dt.datetime.now(dt.timezone.utc)+
                                          dt.timedelta(hours=6)).isoformat()},
            "checked_utc":SCOUT.utc()})
        # Previous anonymous 429 must not block a verified keyed source
        # research retry; the normal five-source gate still applies.
        with mock.patch.dict(os.environ,{"OPENALEX_API_KEY":"TestKey_1234567890123456"}):
            result=SCOUT.run(self.root,self.program,fetcher=sample,
                             backstop=lambda _:[],batch=1,workers=1)
        self.assertEqual(result["source_evidence_automatically_documented"],1)
        self.assertEqual(result["requests_skipped_due_to_provider_cooldown"],0)
        after=STAGE2.read(state)
        self.assertEqual(after["openalex_credential_mode"],"keyed")
        self.assertNotIn(endpoint,after["blocked_until_utc"])

    def test_research_queries_rotate_without_weakening_claim_gate(self):
        order=self.order(1)
        seen=[]
        def empty(query):
            seen.append(query)
            return []
        self.assertEqual(SCOUT.sources_for_topic(
            self.root,STAGE2,order,empty,lambda _:[]),"needs_more_research")
        self.assertEqual(SCOUT.sources_for_topic(
            self.root,STAGE2,order,empty,lambda _:[]),"needs_more_research")
        self.assertEqual(seen,SCOUT.query_variants("Houseplant Rescue Guide")[:2])
        packet=STAGE2.read(
            self.area/"stage-02/literature-candidates/AGRI-001--r001.json")
        self.assertEqual(packet["search_round"],1)
        self.assertFalse(packet["stage3_handoff"])
        self.assertFalse((self.area/"stage-02/source-evidence/AGRI-001--r001.json").exists())

if __name__=="__main__":
    unittest.main()
