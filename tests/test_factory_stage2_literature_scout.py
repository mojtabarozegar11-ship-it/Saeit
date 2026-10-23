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
        "contrasting controlled agricultural treatments"+str(n)+"."
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

    def test_bounded_page_exploration_has_no_weaker_evidence_gate(self):
        seen=[]
        def no_network_records(endpoint, params, timeout=10):
            seen.append((endpoint, params["page"], params["search"]))
            return {"results":[]}
        order=self.order(1)
        with mock.patch.object(SCOUT, "request_json", no_network_records):
            self.assertEqual("needs_more_research",
                             SCOUT.sources_for_topic(self.root,STAGE2,order,
                                                     SCOUT.fetch_openalex,lambda _:[]))
            self.assertEqual("needs_more_research",
                             SCOUT.sources_for_topic(self.root,STAGE2,order,
                                                     SCOUT.fetch_openalex,lambda _:[]))
        self.assertEqual([1,1],[x[1] for x in seen])
        evidence=self.area/"stage-02/source-evidence/AGRI-001--r001.json"
        self.assertFalse(evidence.exists())
        candidate=STAGE2.read(self.area/"stage-02/literature-candidates/AGRI-001--r001.json")
        self.assertEqual(candidate["source_search_page"],1)
        self.assertEqual(candidate["evidence_gap_reason"],
                         "under_four_topic_relevant_article_abstracts")
        with self.assertRaisesRegex(ValueError,"SCOUT_BAD_BOUNDED_RESULTS_PAGE"):
            SCOUT.fetch_openalex("safe agricultural topic",page=7)

    def test_full_query_page_grid_is_explored_before_long_cooldown(self):
        order=self.order(1)
        variants=SCOUT.query_variants("Houseplant Rescue Guide")
        searches=[]
        def indexed_empty(endpoint, params, timeout=10):
            searches.append((params["search"],params["page"]))
            return {"results":[]}
        with mock.patch.object(SCOUT,"request_json",indexed_empty):
            for _ in range(len(variants)+1):
                self.assertEqual("needs_more_research",
                                 SCOUT.sources_for_topic(
                                     self.root,STAGE2,order,
                                     SCOUT.fetch_openalex,lambda _:[]))
        self.assertEqual(searches,[(q,1) for q in variants]+[(variants[0],2)])
        candidate=STAGE2.read(
            self.area/"stage-02/literature-candidates/AGRI-001--r001.json")
        self.assertEqual(candidate["source_search_page"],2)
        self.assertEqual(SCOUT.retry_delay(candidate,"Houseplant Rescue Guide"),
                         dt.timedelta(minutes=15))

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
        # Each claim must match the abstract of its own linked DOI, not
        # an unrelated paper at the same list position.
        source_by_id={s["id"]:s for s in evidence["sources"]}
        for claim in evidence["claims"]:
            source=source_by_id[claim["source_ids"][0]]
            article_number=int(source["doi"].rsplit(".",1)[1])
            original=SCOUT.abstract_from_index(
                study("Houseplant Rescue Guide",article_number)[
                    "abstract_inverted_index"])
            self.assertIn(claim["statement"],original)
        self.assertEqual(STAGE2.stage2_loop(self.root,batch=1)[
            "newly_completed_research_dossiers"],1)
        packet=STAGE2.read(self.area/"stage-03/inbox/WO-00000001--r001.json")
        self.assertFalse(packet["independent_expert_review"])
        self.assertFalse(packet["quality1000_approved"])
        self.assertFalse(packet["public_distribution_allowed"])

    def test_four_independent_papers_may_supply_five_distinct_real_claims(self):
        title="Houseplant Rescue Guide"
        papers=sample(title)[:4]
        original=SCOUT.abstract_from_index(papers[0]["abstract_inverted_index"])
        second=(
            "Houseplant experiments also found significant differences in "
            "growth responses across irrigation conditions in repeated "
            "greenhouse observation cycles."
        )
        papers[0]["abstract_inverted_index"]=indexed(
            original.replace(" We recorded", " "+second+" We recorded",1))
        selected=SCOUT.select_papers(papers,SCOUT.keys(title),STAGE2)
        result=SCOUT.evidence_from_papers(self.order(1),1,selected,STAGE2)
        self.assertIsNotNone(result)
        self.assertEqual(len(result["sources"]),4)
        self.assertEqual(len(result["claims"]),5)
        self.assertEqual(len({item["statement"] for item in result["claims"]}),5)
        first_abstract=SCOUT.abstract_from_index(papers[0]["abstract_inverted_index"])
        self.assertTrue(any(item["statement"] in first_abstract
                            for item in result["claims"]))
        self.assertEqual(STAGE2.validate_evidence(result,self.order(1),1)[
            "source_count"],4)
        self.assertFalse(result["public_distribution_allowed"])
        self.assertFalse(result["scientific_review_completed"])

    def test_four_papers_without_genuine_fifth_passage_stay_blocked(self):
        title="Houseplant Rescue Guide"
        raw=sample(title)[:4]
        for article in raw:
            body=SCOUT.abstract_from_index(article["abstract_inverted_index"])
            # Only the first sentence now mentions the relevant topic:
            # four sources alone cannot fabricate a fifth topical passage.
            body=body.replace("treated ornamental crops","treated field crops")
            article["abstract_inverted_index"]=indexed(body)
        papers=SCOUT.select_papers(raw,SCOUT.keys(title),STAGE2)
        self.assertIsNone(SCOUT.evidence_from_papers(
            self.order(1),1,papers,STAGE2))
        duplicates=SCOUT.select_papers(sample(title)[:5],
                                       SCOUT.keys(title),STAGE2)
        for paper in duplicates:
            paper["support_sentence"]=duplicates[0]["support_sentence"]
        self.assertIsNone(SCOUT.evidence_from_papers(
            self.order(1),1,duplicates,STAGE2))

    def test_existing_intact_v2_cache_promotes_without_api_call(self):
        title="Houseplant Rescue Guide"
        papers=SCOUT.select_papers(sample(title),SCOUT.keys(title),STAGE2)
        order=self.order(1)
        packet={
            "schema":SCOUT.SCHEMA,
            "source_product_id":"AGRI-001","order_id":order["id"],
            "scout_algorithm_version":"v2-relevance-provenance",
            "status":"indexed_references_found_require_additional_research",
            "search_round":0,"checked_utc":SCOUT.utc(),
            "indexed_abstract_candidates":papers,
            "candidate_sha256":SCOUT.sha(papers)
        }
        STAGE2.atomic(self.area/"stage-02/literature-candidates/AGRI-001--r001.json",
                      packet)
        def no_network(_):
            raise AssertionError("Cannot fetch when intact evidence is already enough")
        result=SCOUT.sources_for_topic(self.root,STAGE2,order,
                                       no_network,no_network)
        self.assertEqual(result,"traceable_abstracts")
        self.assertTrue((self.area/"stage-02/source-evidence/AGRI-001--r001.json").exists())

    def test_normalized_scientific_synonyms_recover_relevant_abstracts(self):
        # English -ing/-ation words stem differently. Synonyms must use
        # the same normalization as indexed paper title and abstract terms.
        self.assertIn("irrig",SCOUT.keys("Watering Guide"))
        self.assertIn("moisture",SCOUT.keys("Watering Guide"))
        self.assertIn("substrate",SCOUT.keys("Potting Guide"))
        self.assertIn("germin",SCOUT.keys("Seedling Guide"))
        self.assertIn("propag",SCOUT.keys("Cutting Guide"))
        self.assertIn(SCOUT.normalize("photosynthesis"),SCOUT.keys("Lighting Guide"))
        self.assertTrue(any("irrigation" in value for value in
                            SCOUT.query_variants("Watering Guide")))
        article=study("Watering Guide",1)
        article["display_name"]=(
            "Evaluating irrigation schedule and soil moisture under "
            "greenhouse growing conditions for ornamental crops")
        finding=(
            "Irrigation scheduling and soil moisture monitoring changed "
            "vegetative growth and root development across repeated "
            "controlled greenhouse treatment groups."
        )
        article["abstract_inverted_index"]=indexed(
            finding+" Researchers recorded irrigation frequency and "
            "moisture content by calibrated sensors in replicated growing "
            "systems. The investigators analyzed measured growth outcomes "
            "with statistical comparisons between monitored and "
            "unmonitored treatment groups. Further independent work "
            "should determine applicability under other climate conditions "
            "and production scales."
        )
        self.assertIsNotNone(SCOUT.usable_paper(
            article,SCOUT.keys("Watering Guide"),STAGE2))

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

    def test_provider_failure_preserves_accumulated_verified_abstracts(self):
        title="Houseplant Rescue Guide"
        order=self.order(1)
        cached=[study(title,n) for n in range(1,5)]
        for paper in cached:
            paper["primary_location"]["landing_page_url"]=(
                "https://one.publisher.org/research")
            paper["primary_location"]["source"]["host_organization_name"]=(
                "Single Publisher")
        self.assertEqual("needs_more_research",
                         SCOUT.sources_for_topic(
                             self.root,STAGE2,order,lambda _:cached,lambda _:[]))
        path=self.area/"stage-02/literature-candidates/AGRI-001--r001.json"
        before=STAGE2.read(path)
        self.assertEqual(before["search_round"],0)
        self.assertGreaterEqual(len(before["indexed_abstract_candidates"]),4)
        def provider_down(_):
            raise TimeoutError("temporary indexed search outage")
        self.assertEqual("api_unavailable",
                         SCOUT.sources_for_topic(
                             self.root,STAGE2,order,provider_down,lambda _:[]))
        after=STAGE2.read(path)
        self.assertEqual(after["search_round"],0)
        self.assertEqual(after["attempted_search_round"],1)
        self.assertEqual(after["indexed_abstract_candidates"],
                         before["indexed_abstract_candidates"])
        self.assertEqual(after["candidate_sha256"],before["candidate_sha256"])
        self.assertFalse((self.area/
                         "stage-02/source-evidence/AGRI-001--r001.json").exists())

    def test_unavailable_provider_does_not_fake_source(self):
        def down(_):
            raise TimeoutError("provider offline")
        got=SCOUT.run(self.root,self.program,fetcher=down,
                      backstop=lambda _:[],batch=1,workers=1)
        self.assertEqual(got["external_provider_unavailable"],1)
        self.assertFalse((self.area/"stage-02/source-evidence/AGRI-001--r001.json").exists())

    def test_safety_sensitive_topic_documented_but_cannot_claim_review(self):
        order=self.order(1)
        order["subject"]="Mushroom pesticide toxicity research"
        papers=SCOUT.select_papers(sample("Houseplant Rescue Guide"),
                                  SCOUT.keys("Houseplant Rescue Guide"),STAGE2)
        result=SCOUT.evidence_from_papers(order,1,papers,STAGE2)
        self.assertIsNotNone(result)
        self.assertTrue(result["safety_sensitive_review_hold"])
        self.assertTrue(result["requires_independent_specialist_review"])
        self.assertFalse(result["scientific_review_completed"])
        self.assertFalse(result["public_distribution_allowed"])


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


    def test_relevant_article_sentence_may_use_one_specific_topic_term(self):
        # Title and full abstract retain multiple relevant keys, while a
        # single true supporting sentence need not repeat the whole title.
        p=study("Houseplant Rescue Guide",1)
        sentence=("Houseplant experiments measured plant growth differences "
                  "under multiple irrigation treatments and environmental "
                  "conditions across consecutive observation periods.")
        abstract=(sentence+" Indoor ornamental specimens were examined. "
                  "Further evidence should be assessed for regional safety "
                  "and commercial applicability before practical use in "
                  "controlled commercial production and educational training.")
        p["abstract_inverted_index"]=indexed(abstract)
        keys=SCOUT.keys("Houseplant Rescue Guide")
        hit=SCOUT.usable_paper(p,keys,STAGE2)
        self.assertIsNotNone(hit, msg={"keys":keys,
                "title":p["display_name"],
                "title_hits":len(set(keys) & {SCOUT.normalize(w) for w in SCOUT.WORD_RE.findall(p["display_name"])}),
                "body_hits":len(set(keys) & {SCOUT.normalize(w) for w in SCOUT.WORD_RE.findall(SCOUT.abstract_from_index(p["abstract_inverted_index"]))}),
                "source_url":p["primary_location"]["landing_page_url"],
                "abstract_len":len(SCOUT.abstract_from_index(p["abstract_inverted_index"])),
                "citation":SCOUT.citation_sentence(
                    SCOUT.abstract_from_index(p["abstract_inverted_index"]),keys)})
        self.assertEqual(hit["support_sentence"],sentence)

    def test_accepted_indexed_location_recovers_article_specific_url(self):
        p=study("Houseplant Rescue Guide",1)
        p["primary_location"]["landing_page_url"]=p["doi"]
        p["best_oa_location"]={"landing_page_url":p["doi"]}
        p["locations"]=[
            {"landing_page_url":"https://unreviewed.example.org/preprint",
             "version":"submittedVersion"},
            {"landing_page_url":"https://university.example.edu/record/123",
             "version":"acceptedVersion"}]
        hit=SCOUT.usable_paper(p,SCOUT.keys("Houseplant Rescue Guide"),STAGE2)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["host"],"university.example.edu")
        self.assertNotIn("unreviewed",hit["url"])

    def test_old_research_packets_get_one_versioned_relevance_retry(self):
        index=STAGE2.read(self.area/"owner-agri200-p0-index.json")
        now=dt.datetime.now(dt.timezone.utc)
        for n in range(1,201):
            packet={
                "schema":SCOUT.SCHEMA,
                "source_product_id":"AGRI-%03d"%n,
                "order_id":index["order_ids_ranked"][n-1],
                "status":"indexed_references_found_require_additional_research",
                "checked_utc":now.isoformat(),
                "search_round":0,
                "scout_algorithm_version":(
                    None if n==1 else SCOUT.SCOUT_ALGO_VERSION)}
            STAGE2.atomic(self.area/"stage-02/literature-candidates"/
                          ("AGRI-%03d"%n+"--r001.json"),packet)
        seen=[]
        def fetch(title):
            seen.append(title)
            return sample("Houseplant Rescue Guide")
        result=SCOUT.run(self.root,self.program,fetcher=fetch,
                         backstop=lambda _:[],batch=1,workers=1)
        self.assertEqual(result["attempted_this_run"],1)
        self.assertEqual(len(seen),1)
        self.assertTrue((self.area/"stage-02/source-evidence/AGRI-001--r001.json").is_file())


    def test_selection_reserves_independent_publishers_beyond_top_twenty(self):
        title="Houseplant Rescue Guide"
        articles=[study(title,n) for n in range(1,26)]
        for article in articles:
            article["publication_year"]=2025
        for article in articles[:22]:
            article["primary_location"]["landing_page_url"]=(
                "https://monopoly.publisher.org/article")
            article["primary_location"]["source"]["host_organization_name"]=(
                "Single Aggregated Publisher")
        selected=SCOUT.select_papers(articles,SCOUT.keys(title),STAGE2)
        self.assertEqual(len(selected),20)
        self.assertGreaterEqual(len({
            SCOUT.registrable_host(p["host"]) for p in selected}),4)
        self.assertEqual(len({
            p["publisher"].casefold() for p in selected}),4)
        self.assertIsNotNone(SCOUT.evidence_from_papers(
            self.order(1),1,selected,STAGE2))


    def test_openalex_query_finds_full_words_and_filters_for_real_abstracts(self):
        with mock.patch.object(SCOUT,"request_json",
                               return_value={"results":[]}) as request:
            self.assertEqual(
                SCOUT.fetch_openalex("irrigation water stress"),[])
        args=request.call_args.args
        self.assertEqual(args[0],SCOUT.SAFE_KEYS["openalex"])
        self.assertEqual(args[1]["search"],"irrigation water stress")
        self.assertEqual(args[1]["filter"],"has_abstract:true,has_doi:true")
        self.assertEqual(args[1]["per_page"],100)
        self.assertIn("abstract_inverted_index",args[1]["select"])
        query_set=SCOUT.query_variants("Houseplant Watering Planner")
        self.assertIn("houseplant watering",query_set)
        self.assertIn("houseplant",query_set)
        self.assertTrue(any(" OR " in q and "irrigation" in q
                            for q in query_set))
        self.assertFalse(any("irrig " in q for q in query_set))

    def test_cached_retry_does_not_discard_new_independent_publishers(self):
        title="Houseplant Rescue Guide"
        order=self.order(1)
        old=[study(title,n) for n in range(1,21)]
        fresh=[study(title,n) for n in range(21,24)]
        for article in old+fresh:
            article["publication_year"]=2025
        for article in old:
            article["primary_location"]["landing_page_url"]=(
                "https://dominant.publisher.org/article")
            article["primary_location"]["source"]["host_organization_name"]=(
                "Dominant Publisher")
        responses=[old,fresh]
        def fetch(_):
            return responses.pop(0)
        first=SCOUT.sources_for_topic(
            self.root,STAGE2,order,fetch,lambda _:[])
        self.assertEqual(first,"needs_more_research")
        second=SCOUT.sources_for_topic(
            self.root,STAGE2,order,fetch,lambda _:[])
        self.assertEqual(second,"traceable_abstracts")
        evidence=STAGE2.read(
            self.area/"stage-02/source-evidence/AGRI-001--r001.json")
        self.assertGreaterEqual(len({
            SCOUT.registrable_host(s["url"].split("/")[2])
            for s in evidence["sources"]}),4)
        self.assertFalse(evidence["public_distribution_allowed"])

    def test_evidence_gap_reports_actual_unmet_gate(self):
        title="Houseplant Rescue Guide"
        order=self.order(1)
        key=SCOUT.keys(title)
        too_few=SCOUT.select_papers(sample(title)[:2],key,STAGE2)
        self.assertEqual(
            SCOUT.evidence_gap_reason(order,too_few),
            "under_four_topic_relevant_article_abstracts")
        single_publisher=sample(title)[:5]
        for item in single_publisher:
            item["primary_location"]["landing_page_url"]=(
                "https://single.publisher.org/articles")
            item["primary_location"]["source"]["host_organization_name"]=(
                "Single Scientific Publisher")
        same_source=SCOUT.select_papers(single_publisher,key,STAGE2)
        self.assertEqual(
            SCOUT.evidence_gap_reason(order,same_source),
            "insufficient_independent_publishers_or_domains")
        without_fifth=SCOUT.select_papers(sample(title)[:4],key,STAGE2)
        for item in without_fifth:
            item["support_sentences"]=[item["support_sentence"]]
        self.assertEqual(
            SCOUT.evidence_gap_reason(order,without_fifth),
            "fifth_distinct_verbatim_claim_unavailable")

    def test_scout_cycle_promotes_new_evidence_without_manual_redeploy(self):
        installer=(BASE/"deploy/install_factory_stage2_literature_scout.sh").read_text()
        self.assertIn("&& /usr/bin/timeout 120s",installer)
        self.assertIn("stage2-research.py --factory-private",installer)
        self.assertIn("awk -v marker=",installer)
        self.assertIn("FACTORY_STAGE2_SCOUT_CRON=UPDATED",installer)

    def test_bounded_three_query_burst_yields_only_real_source_packet(self):
        seen=[]
        title="Houseplant Rescue Guide"
        variants=SCOUT.query_variants(title)
        def fetch(query):
            seen.append(query)
            return [] if len(seen)==1 else sample(title)
        result=SCOUT.run(self.root,self.program,fetcher=fetch,
                         backstop=lambda _:[],batch=1,workers=1,query_burst=3)
        self.assertEqual(result["attempted_this_run"],1)
        self.assertEqual(result["source_evidence_automatically_documented"],1)
        self.assertEqual(result["bounded_source_search_rounds_this_run"],2)
        self.assertEqual(result["max_query_variants_per_topic_this_run"],3)
        self.assertEqual(seen,variants[:2])
        self.assertTrue((self.area/"stage-02/source-evidence/AGRI-001--r001.json").is_file())

    def test_burst_never_retries_provider_quota_failure(self):
        attempts=[]
        def unavailable(q):
            attempts.append(q)
            raise SCOUT.ProviderCoolingDown("SCOUT_PROVIDER_COOLING_DOWN")
        result=SCOUT.run(self.root,self.program,fetcher=unavailable,
                         backstop=lambda _:[],batch=1,workers=1,query_burst=3)
        self.assertEqual(attempts,["Houseplant Rescue Guide"])
        self.assertEqual(result["bounded_source_search_rounds_this_run"],1)
        self.assertEqual(result["requests_skipped_due_to_provider_cooldown"],1)
        self.assertEqual(result["source_evidence_automatically_documented"],0)

    def test_progressive_short_retry_keeps_exhausted_search_on_long_cooldown(self):
        title="Houseplant Rescue Guide"
        fresh={"status":"indexed_references_found_require_additional_research",
               "scout_algorithm_version":SCOUT.SCOUT_ALGO_VERSION,
               "search_round":1}
        self.assertEqual(SCOUT.retry_delay(fresh,title),dt.timedelta(minutes=15))
        first_sweep=dict(fresh,search_round=4*len(SCOUT.query_variants(title))-1)
        self.assertEqual(SCOUT.retry_delay(first_sweep,title),dt.timedelta(minutes=15))
        full=dict(fresh,search_round=8*len(SCOUT.query_variants(title))-1)
        self.assertEqual(SCOUT.retry_delay(full,title),dt.timedelta(hours=8))
        denied=dict(fresh,status="external_research_api_unavailable")
        self.assertEqual(SCOUT.retry_delay(denied,title),dt.timedelta(minutes=12))
        self.assertEqual(SCOUT.retry_delay(dict(fresh,scout_algorithm_version="v7-multiphase-topic-specific-query"),title),dt.timedelta(0))
        with self.assertRaisesRegex(RuntimeError,"SCOUT_INVALID_SEARCH_ROUND"):
            SCOUT.retry_delay(dict(fresh,search_round=10001),title)
        with self.assertRaisesRegex(ValueError,"SCOUT_INVALID_QUERY_BURST"):
            SCOUT.run(self.root,self.program,batch=1,workers=1,query_burst=4)

    def test_extended_pages_explore_new_indexed_records_before_repeat(self):
        order=self.order(1)
        queries=SCOUT.query_variants("Houseplant Rescue Guide")
        candidate_path=(self.area/"stage-02/literature-candidates/"
                        "AGRI-001--r001.json")
        STAGE2.atomic(candidate_path,{
            "schema":SCOUT.SCHEMA,"source_product_id":"AGRI-001",
            "order_id":order["id"],
            "status":"indexed_references_found_require_additional_research",
            "checked_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "search_round":4*len(queries)-1,
            "scout_algorithm_version":SCOUT.SCOUT_ALGO_VERSION})
        seen=[]
        def empty_provider(endpoint,params,timeout=10):
            seen.append((params["search"],params["page"]))
            return {"results":[]}
        with mock.patch.object(SCOUT,"request_json",empty_provider):
            self.assertEqual(SCOUT.sources_for_topic(
                self.root,STAGE2,order,SCOUT.fetch_openalex,lambda _:[]),
                "needs_more_research")
        self.assertEqual(seen,[(queries[0],5)])
        with mock.patch.object(SCOUT,"request_json",empty_provider):
            SCOUT.fetch_openalex("houseplant science",page=8)
        self.assertEqual(seen[-1],("houseplant science",8))
        with self.assertRaisesRegex(ValueError,"SCOUT_BAD_BOUNDED_RESULTS_PAGE"):
            SCOUT.fetch_openalex("houseplant science",page=9)

    def test_one_off_recovery_only_targets_real_evidence_gaps(self):
        now=dt.datetime.now(dt.timezone.utc)
        index=STAGE2.read(self.area/"owner-agri200-p0-index.json")
        for rank,ident in enumerate(index["order_ids_ranked"],1):
            order=self.order(rank)
            title=next(e["title"] for e in order["editions"]
                       if e["locale"]=="en-US")
            STAGE2.atomic(self.area/"stage-02/literature-candidates"/
                          ("AGRI-%03d"%rank+"--r001.json"),{
                "schema":SCOUT.SCHEMA,
                "source_product_id":"AGRI-%03d"%rank,
                "order_id":ident,
                "status":"indexed_references_found_require_additional_research",
                "checked_utc":now.isoformat(),
                "search_round":4*len(SCOUT.query_variants(title))-1,
                "scout_algorithm_version":SCOUT.SCOUT_ALGO_VERSION,
                "evidence_gap_reason":(
                    "under_four_topic_relevant_article_abstracts"
                    if rank==1 else "unclassified")})
        attempted=[]
        def empty_search(query):
            attempted.append(query)
            return []
        ordinary=SCOUT.run(self.root,self.program,fetcher=empty_search,
                           backstop=lambda _:[],batch=1,workers=1)
        self.assertEqual(ordinary["attempted_this_run"],0)
        urgent=SCOUT.run(self.root,self.program,fetcher=empty_search,
                         backstop=lambda _:[],batch=1,workers=1,
                         expedite_gap_research=True)
        self.assertEqual(urgent["attempted_this_run"],1)
        self.assertEqual(urgent["expedited_unresolved_evidence_gaps"],1)
        self.assertEqual(urgent["source_evidence_automatically_documented"],0)
        self.assertEqual(len(attempted),1)
        self.assertTrue(urgent["evidence_review_and_release_gates_unchanged"])

    def test_scheduled_quick_retry_moves_only_eligible_gap(self):
        now=dt.datetime.now(dt.timezone.utc)
        index=STAGE2.read(self.area/"owner-agri200-p0-index.json")
        for rank,ident in enumerate(index["order_ids_ranked"],1):
            checked=(now-dt.timedelta(minutes=16) if rank==1 else now)
            STAGE2.atomic(self.area/"stage-02/literature-candidates"/
                          ("AGRI-%03d"%rank+"--r001.json"),{
                "schema":SCOUT.SCHEMA,"source_product_id":"AGRI-%03d"%rank,
                "order_id":ident,
                "status":"indexed_references_found_require_additional_research",
                "checked_utc":checked.isoformat(),
                "search_round":0,
                "scout_algorithm_version":SCOUT.SCOUT_ALGO_VERSION})
        observed=[]
        def fetch(query):
            observed.append(query)
            return sample("Houseplant Rescue Guide")
        report=SCOUT.run(self.root,self.program,fetcher=fetch,
                         backstop=lambda _:[],batch=1,workers=1)
        self.assertEqual(report["attempted_this_run"],1)
        self.assertEqual(report["source_evidence_automatically_documented"],1)
        self.assertEqual(observed,[SCOUT.query_variants("Houseplant Rescue Guide")[1]])

if __name__=="__main__":
    unittest.main()
