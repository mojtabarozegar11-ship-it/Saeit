"""End-to-end tests: real new private prototype ZIP, durable queue, UI, release gates."""
import copy
import http.client
import importlib.util
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts"/"astra_v2_private_pipeline.py"
PRODUCT=ROOT/"product_prototypes"/"orchard_decision_audit"
spec=importlib.util.spec_from_file_location("astra_v2_private_pipeline_test",str(SCRIPT))
pipeline=importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)
spec=importlib.util.spec_from_file_location("orchard_local_ui_api_tests",str(PRODUCT/"serve_local.py"))
server_module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(server_module)


def brief(identifier="orchard_mvp_001"):
    return {
        "brief_id":identifier,
        "builder":pipeline.BUILDER,
        "development_scope":"private_reference_prototype",
        "publication_allowed":False,
        "market_demand_verified":False,
        "paid_api_budget":0,
        "problem":"Testable long-horizon orchard capital investment audit with operator data",
    }


class PrivateManufacturingTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=pipeline.safe_root(Path(t.name)/"factory-private")

    def test_distributed_product_runs_standalone_self_test(self):
        pipeline.enqueue(self.root, brief())
        result=pipeline.tick(self.root)
        self.assertEqual(result["status"],"PRIVATE_QA_PASSED",result)
        archive=next(self.root.glob("artifact-*.zip"))
        unpack=self.root/"consumer-unpack"
        unpack.mkdir()
        with zipfile.ZipFile(archive) as z:
            z.extractall(unpack)
        script=unpack/"orchard_decision_audit"/"self_test.py"
        self.assertTrue(script.exists())
        proc=subprocess.run([sys.executable,str(script)],
                            capture_output=True,text=True,timeout=10)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertIn("ORCHARD_PRODUCT_SELF_TEST=PASS",proc.stdout)

    def test_delivered_application_has_annual_audit_and_csv_export(self):
        html=(PRODUCT/"index.html").read_text()
        js=(PRODUCT/"app.js").read_text()
        self.assertIn('id="annual-audit"',html)
        self.assertIn('id="download-csv"',html)
        self.assertIn('id="print-report"',html)
        self.assertIn("renderAnnualTrace(data)",js)
        self.assertIn("function auditCSV(data)",js)
        self.assertIn("function exportCSV(",js)

    def test_two_independent_builders_produce_two_real_distinct_product_families(self):
        first=brief("orchard_distinct_first")
        second=brief("procurement_distinct_second")
        second["builder"]=pipeline.PROCUREMENT_BUILDER
        pipeline.enqueue(self.root,first)
        pipeline.enqueue(self.root,second)
        one=pipeline.tick(self.root)
        two=pipeline.tick(self.root)
        self.assertEqual(one["status"],"PRIVATE_QA_PASSED",one)
        self.assertEqual(two["status"],"PRIVATE_QA_PASSED",two)
        self.assertEqual(one["new_distinct_product_versions"],1)
        self.assertEqual(two["new_distinct_product_versions"],1)
        statuses=pipeline.status(self.root)
        self.assertEqual(statuses["distinct_private_product_families"],2)
        self.assertEqual(statuses["distinct_private_qa_artifact_versions"],2)
        self.assertEqual(statuses["published_products"],0)
        archives=sorted(self.root.glob("artifact-*.zip"))
        self.assertEqual(len(archives),2)
        members=[zipfile.ZipFile(archive).namelist() for archive in archives]
        self.assertTrue(any("farm_procurement_audit/procurement_audit.py" in group
                            for group in members))
        self.assertTrue(any("orchard_decision_audit/decision_audit.py" in group
                            for group in members))
        reports=[json.loads(p.read_text()) for p in self.root.glob("qa-*.json")]
        self.assertEqual({r["source_builder"] for r in reports},
                         {pipeline.BUILDER,pipeline.PROCUREMENT_BUILDER})
        for report in reports:
            self.assertIsNone(report["quality_score"])
            self.assertFalse(report["sale_ready"])
            self.assertFalse(report["owner_publication_approval"])
            self.assertFalse(report["evidence_of_willingness_to_pay"])

    def test_second_builder_rebuild_does_not_fabricate_third_product(self):
        b=brief("procurement_first_build")
        b["builder"]=pipeline.PROCUREMENT_BUILDER
        pipeline.enqueue(self.root,b)
        self.assertEqual(pipeline.tick(self.root)["new_distinct_product_versions"],1)
        b["brief_id"]="procurement_repeated_sources"
        pipeline.enqueue(self.root,b)
        self.assertEqual(pipeline.tick(self.root)["new_distinct_product_versions"],0)
        self.assertEqual(pipeline.status(self.root)["distinct_private_product_families"],1)
        self.assertEqual(pipeline.tick(self.root)["status"],"NO_ELIGIBLE_WORK")

    def test_unsupported_builder_never_makes_files_or_paid_calls(self):
        item=brief("unsupported_custom_model")
        item["builder"]="llm_unrestricted_paid_builder"
        with self.assertRaises(ValueError):
            pipeline.enqueue(self.root,item)
        self.assertEqual(list(self.root.glob("artifact-*.zip")),[])

    def test_three_independent_specialist_families_are_real_and_distinct(self):
        three=[
            ("third_orchard_case",pipeline.BUILDER),
            ("third_procurement_case",pipeline.PROCUREMENT_BUILDER),
            ("third_water_case",pipeline.WATER_BUILDER),
        ]
        for name,builder in three:
            obj=brief(name)
            obj["builder"]=builder
            self.assertTrue(pipeline.enqueue(self.root,obj)["new_job"])
        outputs=[pipeline.tick(self.root) for _ in three]
        self.assertTrue(all(o["status"]=="PRIVATE_QA_PASSED" for o in outputs),outputs)
        self.assertEqual(sum(o["new_distinct_product_versions"] for o in outputs),3)
        status=pipeline.status(self.root)
        self.assertEqual(status["distinct_private_product_families"],3)
        self.assertEqual(status["distinct_private_qa_artifact_versions"],3)
        self.assertEqual(status["published_products"],0)
        self.assertEqual(pipeline.tick(self.root)["status"],"NO_ELIGIBLE_WORK")
        self.assertEqual(
            {json.loads(p.read_text())["source_builder"] for p in self.root.glob("qa-*.json")},
            {pipeline.BUILDER,pipeline.PROCUREMENT_BUILDER,pipeline.WATER_BUILDER},
        )
        paths=[zipfile.ZipFile(p).namelist() for p in self.root.glob("artifact-*.zip")]
        self.assertTrue(any("farm_water_land_margin_audit/water_margin_audit.py" in names
                            for names in paths))

    def test_water_builder_is_self_contained_and_does_not_authorize_sale(self):
        obj=brief("water_research_reference")
        obj["builder"]=pipeline.WATER_BUILDER
        pipeline.enqueue(self.root,obj)
        result=pipeline.tick(self.root)
        self.assertEqual(result["status"],"PRIVATE_QA_PASSED",result)
        dest=next(self.root.glob("artifact-*.zip"))
        with tempfile.TemporaryDirectory() as t:
            with zipfile.ZipFile(dest) as z:z.extractall(t)
            test=Path(t)/"farm_water_land_margin_audit"/"self_test.py"
            proc=subprocess.run([sys.executable,str(test)],capture_output=True,text=True,timeout=10)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertIn("INDEPENDENT_SELF_TEST=PASS",proc.stdout)
        qa=json.loads(next(self.root.glob("qa-*.json")).read_text())
        self.assertIsNone(qa["quality_score"])
        self.assertFalse(qa["public_deployment_allowed"])
        self.assertFalse(qa["real_payment_allowed"])
        self.assertFalse(qa["evidence_of_willingness_to_pay"])

    def test_new_private_product_build_and_immutable_manifest(self):
        first=pipeline.enqueue(self.root,brief())
        self.assertTrue(first["new_job"])
        result=pipeline.tick(self.root)
        self.assertEqual(result["status"],"PRIVATE_QA_PASSED",result)
        self.assertEqual(result["new_distinct_product_versions"],1)
        self.assertEqual(result["new_products_for_sale"],0)
        self.assertIsNone(result["qa_score"])
        archives=list(self.root.glob("artifact-*.zip"))
        self.assertEqual(len(archives),1)
        with zipfile.ZipFile(archives[0]) as z:
            self.assertEqual(z.testzip(),None)
            members=z.namelist()
            self.assertIn("orchard_decision_audit/index.html",members)
            self.assertIn("orchard_decision_audit/app.js",members)
            self.assertIn("orchard_decision_audit/serve_local.py",members)
            self.assertIn("orchard_decision_audit/decision_audit.py",members)
        manifests=list(self.root.glob("qa-*.json"))
        self.assertEqual(len(manifests),1)
        data=json.loads(manifests[0].read_text())
        self.assertFalse(data["sale_ready"])
        self.assertIsNone(data["quality_score"])
        self.assertGreater(len(data["blocking_gates"]),3)
        self.assertFalse(data["owner_publication_approval"])
        self.assertFalse(data["independent_domain_review"])

    def test_same_brief_does_not_create_duplicate_job_or_product(self):
        one=pipeline.enqueue(self.root,brief())
        self.assertEqual(pipeline.enqueue(self.root,brief())["status"],"UNCHANGED")
        self.assertEqual(one["job_id"],1)
        self.assertEqual(pipeline.tick(self.root)["new_distinct_product_versions"],1)
        second=pipeline.tick(self.root)
        self.assertEqual(second["status"],"NO_ELIGIBLE_WORK")
        self.assertEqual(pipeline.status(self.root)["distinct_private_qa_artifact_versions"],1)

    def test_different_brief_same_source_is_not_claimed_distinct_product(self):
        pipeline.enqueue(self.root,brief("orchard_first"))
        pipeline.enqueue(self.root,brief("orchard_second"))
        self.assertEqual(pipeline.tick(self.root)["new_distinct_product_versions"],1)
        self.assertEqual(pipeline.tick(self.root)["new_distinct_product_versions"],0)
        s=pipeline.status(self.root)
        self.assertEqual(s["distinct_private_qa_artifact_versions"],1)
        self.assertEqual(s["queues"]["PRIVATE_QA_PASSED"],2)

    def test_status_is_durable_across_connection_reopens(self):
        pipeline.enqueue(self.root,brief())
        before=pipeline.status(self.root)
        self.assertEqual(before["queues"]["QUEUED"],1)
        result=pipeline.tick(self.root)
        self.assertEqual(result["status"],"PRIVATE_QA_PASSED")
        after=pipeline.status(self.root)
        self.assertNotIn("QUEUED",after["queues"])
        self.assertEqual(after["published_products"],0)
        self.assertIsNone(after["verified_revenue"])

    def test_interrupted_job_resumes_after_simulated_worker_death(self):
        pipeline.enqueue(self.root, brief("crashed_worker_job"))
        with pipeline.locked(self.root), pipeline.database(self.root) as con:
            with con:
                con.execute("UPDATE jobs SET stage='BUILDING',attempts=1")
        result=pipeline.tick(self.root)
        self.assertEqual(result["status"], "PRIVATE_QA_PASSED", result)
        self.assertEqual(pipeline.status(self.root)["distinct_private_qa_artifact_versions"], 1)
        with pipeline.database(self.root) as con:
            state=con.execute("SELECT stage,attempts FROM jobs").fetchone()
        self.assertEqual(state, ("PRIVATE_QA_PASSED",2))

    def test_thrice_interrupted_job_is_quarantined_without_infinite_retries(self):
        pipeline.enqueue(self.root, brief("irrecoverable_worker_job"))
        with pipeline.locked(self.root), pipeline.database(self.root) as con:
            with con:
                con.execute("UPDATE jobs SET stage='BUILDING',attempts=3")
        result=pipeline.tick(self.root)
        self.assertEqual(result["status"],"NO_ELIGIBLE_WORK")
        with pipeline.database(self.root) as con:
            state=con.execute("SELECT stage,attempts,last_error FROM jobs").fetchone()
        self.assertEqual(state,("FAILED_REVIEW",3,"RETRY_LIMIT_EXCEEDED"))
        self.assertEqual(pipeline.status(self.root)["distinct_private_qa_artifact_versions"],0)

    def test_multiple_stalled_workers_are_recovered_before_new_work(self):
        pipeline.enqueue(self.root, brief("stalled_early"))
        pipeline.enqueue(self.root, brief("waiting_later"))
        with pipeline.locked(self.root), pipeline.database(self.root) as con:
            with con:
                con.execute("UPDATE jobs SET stage='BUILDING',attempts=1 WHERE id=1")
        run=pipeline.tick(self.root)
        self.assertEqual(run["status"],"PRIVATE_QA_PASSED",run)
        self.assertEqual(run["job_id"],1)
        self.assertEqual(pipeline.tick(self.root)["new_distinct_product_versions"],0)
        self.assertEqual(pipeline.tick(self.root)["status"],"NO_ELIGIBLE_WORK")

    def test_private_inbox_auto_enqueue_and_replay_are_deduplicated(self):
        inbox=self.root/"incoming"
        inbox.mkdir(mode=0o700)
        orchard=brief("inbox_autonomous_orchard")
        procurement=brief("inbox_autonomous_procurement")
        procurement["builder"]=pipeline.PROCUREMENT_BUILDER
        (inbox/"a.json").write_text(json.dumps(orchard))
        (inbox/"b.json").write_text(json.dumps(procurement))
        self.assertEqual(pipeline.tick(self.root)["new_distinct_product_versions"],1)
        self.assertEqual(pipeline.tick(self.root)["new_distinct_product_versions"],1)
        self.assertEqual(pipeline.tick(self.root)["status"],"NO_ELIGIBLE_WORK")
        self.assertEqual(pipeline.status(self.root)["distinct_private_product_families"],2)
        self.assertEqual(pipeline.status(self.root)["queues"]["PRIVATE_QA_PASSED"],2)

    def test_invalid_or_paid_private_inbox_cannot_block_eligible_task(self):
        inbox=self.root/"incoming";inbox.mkdir()
        (inbox/"bad.json").write_text('{"broken"')
        malicious=brief("invalid_paid_job")
        malicious["paid_api_budget"]=100
        (inbox/"paid.json").write_text(json.dumps(malicious))
        (inbox/"good.json").write_text(json.dumps(brief("free_valid_job")))
        outcome=pipeline.tick(self.root)
        self.assertEqual(outcome["status"],"PRIVATE_QA_PASSED")
        self.assertEqual(pipeline.status(self.root)["queues"]["PRIVATE_QA_PASSED"],1)
        self.assertEqual(pipeline.intake_private_briefs(self.root)["rejected"],2)

    def test_symlink_inbox_rejected_before_task_execution(self):
        with tempfile.TemporaryDirectory() as external:
            (self.root/"incoming").symlink_to(external)
            with self.assertRaisesRegex(ValueError,"regular directory"):
                pipeline.tick(self.root)

    def test_invalid_builder_approval_or_fake_verified_demand_blocked(self):
        for patch in (
            {"builder":"shell_script"},
            {"publication_allowed":True},
            {"market_demand_verified":True},
            {"paid_api_budget":1},
            {"development_scope":"public_release"},
            {"problem":"tiny"},
        ):
            with self.subTest(patch=patch):
                item=brief();item.update(patch)
                with self.assertRaises(ValueError):
                    pipeline.enqueue(self.root,item)
        self.assertEqual(pipeline.status(self.root)["queues"],{})

    def test_unsafely_broad_output_directory_rejected(self):
        for value in ("/","/tmp"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    pipeline.safe_root(value)

    def test_missing_file_of_allowlisted_source_is_protected_by_precheck(self):
        names={p.name for p in PRODUCT.iterdir() if p.is_file()}
        self.assertTrue(set(pipeline.FILES).issubset(names))

    def test_script_demo_traces_actual_chain_without_persisting_server_state(self):
        proc=subprocess.run([sys.executable,str(SCRIPT),"demo"],
                            capture_output=True,text=True,timeout=60)
        self.assertEqual(proc.returncode,0,proc.stderr)
        obj=json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(obj["result"],"PASSED")
        self.assertEqual(obj["new_distinct_private_versions"],1)
        self.assertEqual(obj["commercial_products_released"],0)


class PrivateBrowserServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=server_module.ThreadingHTTPServer(("127.0.0.1",0),server_module.Handler)
        cls.port=cls.server.server_address[1]
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)
        cls.server.server_close()

    def send(self,method,path,body=None,headers=None):
        conn=http.client.HTTPConnection("127.0.0.1",self.port,timeout=5)
        try:
            head={"Host":"127.0.0.1:"+str(self.port)}
            if headers:head.update(headers)
            if body is not None:
                if not isinstance(body,bytes):body=body.encode()
                head["Content-Length"]=str(len(body))
            conn.request(method,path,body=body,headers=head)
            res=conn.getresponse()
            return res.status,dict(res.getheaders()),res.read()
        finally:
            conn.close()

    def post(self,payload,headers=None):
        h={"Origin":"http://127.0.0.1:"+str(self.port),
           "Content-Type":"application/json"}
        if headers:h.update(headers)
        return self.send("POST","/api/analyze",json.dumps(payload),h)

    def test_local_assets_have_privacy_security_headers(self):
        for path in ("/","/app.js","/style.css","/sample.json"):
            with self.subTest(path=path):
                status,h,body=self.send("GET",path)
                self.assertEqual(status,200)
                self.assertGreater(len(body),20)
                self.assertEqual(h.get("X-Frame-Options"),"DENY")
                self.assertEqual(h.get("Cache-Control"),"no-store")
                self.assertIn("default-src 'none'",h.get("Content-Security-Policy",""))

    def test_complete_example_flows_over_same_origin_local_api(self):
        data=json.loads((PRODUCT/"example_synthetic.json").read_text())
        status,headers,body=self.post(data)
        self.assertEqual(status,200,body)
        report=json.loads(body)
        self.assertEqual(report["leading_option_by_base_npv_not_advice"],"Replace Orchard Block")
        self.assertFalse(report["store_listing_authorized"])
        self.assertFalse(report["sources_independently_verified"])
        self.assertEqual(len(report["scenarios"]["base"]),2)

    def test_wrong_origin_request_is_rejected(self):
        data=json.loads((PRODUCT/"example_synthetic.json").read_text())
        st,_,body=self.post(data,{"Origin":"https://malicious.example"})
        self.assertEqual(st,403)
        self.assertIn(b"CROSS_ORIGIN_REQUEST_BLOCKED",body)

    def test_missing_origin_blocked_even_with_correct_content_type(self):
        st,_,body=self.send("POST","/api/analyze","{}",{"Content-Type":"application/json"})
        self.assertEqual(st,403)

    def test_host_rebinding_blocked(self):
        st,_,body=self.send("GET","/",headers={"Host":"evil.example"})
        self.assertEqual(st,403)
        self.assertIn(b"INVALID_HOST",body)

    def test_oversized_and_invalid_payload_returns_safe_error(self):
        st,_,body=self.send("POST","/api/analyze","{}",
            {"Origin":"http://127.0.0.1:"+str(self.port),
             "Content-Type":"application/json","Content-Length":"200001"})
        self.assertIn(st,(413,422))
        st,_,body=self.post({"random_key":"hi"})
        self.assertEqual(st,422)

    def test_no_cors_headers_emitted(self):
        st,h,_=self.send("GET","/")
        self.assertEqual(st,200)
        self.assertNotIn("Access-Control-Allow-Origin",h)

    def test_js_syntax_when_node_is_available(self):
        node=shutil.which("node")
        if not node:self.skipTest("Node not installed")
        for f in ("app.js",):
            p=subprocess.run([node,"--check",str(PRODUCT/f)],
                             capture_output=True,text=True,timeout=8)
            self.assertEqual(p.returncode,0,p.stderr)


if __name__=="__main__":
    unittest.main()
