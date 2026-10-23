"""Exercise five real MojPlayWin robot tasks with offline/side-effect-safe probes."""
import importlib.util
from pathlib import Path
import tempfile
import json
import unittest
from unittest.mock import patch
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("mpw_exec_robots",ROOT/"scripts/mpw_main_private_execution_robots.py")
robots=importlib.util.module_from_spec(spec);spec.loader.exec_module(robots)

class MainRobotsTests(unittest.TestCase):
    def test_five_distinct_concrete_robots(self):
        self.assertEqual(len(robots.ROBOTS),5)
        self.assertEqual(len(set(robots.ROBOTS)),5)

    def test_site_route_http_checked_only_for_main_domain(self):
        requests=[]
        def fake(path,method):
            requests.append((path,method))
            return (200,b"")
        result=robots.route_robot(fake)
        self.assertEqual(result["healthy"],6)
        self.assertEqual(result["status"],"ok")
        self.assertEqual(requests,[(p,"HEAD") for p in robots.MAIN_ROUTES])
        self.assertEqual(result["mutations"],0)

    def test_site_route_warning_when_one_unavailable(self):
        def fake(path,method):
            return 404 if path=="/research/" else 200,b""
        result=robots.route_robot(fake)
        self.assertEqual(result["status"],"warning")
        self.assertEqual(result["healthy"],5)

    def test_main_domain_allowlist_is_closed(self):
        with self.assertRaisesRegex(RuntimeError,"UNAPPROVED_PATH"):
            robots.public_probe("/mojtaba.roozegar/")
        with self.assertRaisesRegex(RuntimeError,"UNAPPROVED_PATH"):
            robots.public_probe("https://example.com/")

    def test_draft_fingerprint_and_review_queue(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            folder=root/"page_content_20261018/drafts";folder.mkdir(parents=True)
            folder.chmod(0o700)
            row={"tenant":"mojplaywin-main","page_path":"/agents/","slug":"safe-guide",
                 "body_markdown":"# Safe guide\n\nEvidence and practical advice.",
                 "source_urls":["https://www.nist.gov","https://www.w3.org"],
                 "language":"en","published":False,"approved_for_publication":False}
            import hashlib
            row["content_sha256"]=hashlib.sha256((row["page_path"]+"\x1f"+row["body_markdown"]).encode()).hexdigest()
            (folder/"safe-guide.json").write_text(json.dumps(row))
            with patch.object(robots,"EVO",root):
                proof=robots.draft_robot()
            self.assertEqual(proof["examined"],1)
            queue=robots.review_queue_robot(proof)
            self.assertEqual(queue["review_tasks_created_or_refreshed"],1)
            self.assertFalse(queue["work_items"][0]["can_auto_approve"])
            self.assertEqual(queue["publications"],0)
            row["body_markdown"]="unverified edited text"
            (folder/"safe-guide.json").write_text(json.dumps(row))
            with patch.object(robots,"EVO",root):
                with self.assertRaisesRegex(RuntimeError,"TAMPER"):
                    robots.draft_robot()

    def test_editorial_links_explicit_html(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);editorial=root/"mpw-editorial"
            (editorial/"agents/example").mkdir(parents=True)
            (editorial/"agents/index.html").write_text("<html>MojPlayWin</html>")
            (editorial/"agents/example/index.html").write_text("<html>MojPlayWin</html>")
            (editorial/"index.html").write_text(
                '<a href="/mpw-editorial/agents/example/index.html">good</a>')
            (editorial/robots.OWNER if hasattr(robots,"OWNER") else editorial/".mpw-editorial-owner.json").write_text(
                json.dumps({"tenant":"mojplaywin-main","scope":"mojplaywin-main-static-mpw-editorial-only","published_articles":1}))
            (root/"editorial_publication_state.json").write_text(
                json.dumps({"tenant":"mojplaywin-main","status":"published_verified_by_external_smoke"}))
            with patch.object(robots,"EVO",root):
                result=robots.editorial_robot(editorial,
                    lambda *args:(200,b"MojPlayWin live public"))
            self.assertEqual(result["status"],"ok")
            self.assertEqual(result["broken_internal_links"],0)
            (editorial/"index.html").write_text(
                '<a href="/mpw-editorial/agents/example/">broken directory route</a>')
            with patch.object(robots,"EVO",root):
                bad=robots.editorial_robot(editorial,
                    lambda *args:(200,b"MojPlayWin live public"))
            self.assertEqual(bad["broken_internal_links"],1)
            self.assertEqual(bad["status"],"warning")

    def test_editorial_over_fifteen_documents_remains_observable(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            editorial=root/"mpw-editorial"
            (editorial/"agents").mkdir(parents=True)
            (editorial/"index.html").write_text("<html>MojPlayWin</html>")
            (editorial/"agents/index.html").write_text("<html>MojPlayWin</html>")
            for number in range(20):
                doc=editorial/"agents"/f"topic-{number}"/"index.html"
                doc.parent.mkdir()
                doc.write_text("<html>MojPlayWin</html>")
            (editorial/".mpw-editorial-owner.json").write_text(json.dumps({
                "tenant":"mojplaywin-main",
                "scope":"mojplaywin-main-static-mpw-editorial-only",
                "published_articles":20}))
            (root/"editorial_publication_state.json").write_text(json.dumps({
                "tenant":"mojplaywin-main",
                "status":"published_verified_by_external_smoke"}))
            with patch.object(robots,"EVO",root):
                result=robots.editorial_robot(editorial,
                    lambda *args:(200,b"MojPlayWin live public"))
            self.assertEqual(result["status"],"ok")
            self.assertEqual(result["published_documents"],22)

    def test_cron_and_evolution_health_detection(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"site_health_v11_port_20261018").mkdir()
            (root/"evolution_runtime_20261018").mkdir()
            report={"tenant":"mojplaywin-main","status":"gen65_operational_private",
                    "active_private_generation":65,
                    "observed_utc":datetime.now(timezone.utc).isoformat()}
            (root/"evolution_runtime_20261018/gen65_operational_report.json").write_text(json.dumps(report))
            (root/"evolution_runtime_20261018/all_77_modules_last_run.json").write_text(
                json.dumps({"tenant":"mojplaywin-main","modules_import_executed":77,
                            "capability_namespaces_active":77,
                            "functional_probes_executed":14,
                            "per_module_capability_registry":[{"loaded":True,
                                "safe_scope":"read_only_private"} for _ in range(77)]}))
            (root/"site_health_v11_port_20261018/last_scan.json").write_text(
                json.dumps({"tenant":"mojplaywin-main","total_agents":11,"runs":[{}]*11}))
            markers={"MPW_V91_MAIN_ONLY_20261018":"17",
                     "MPW_V11_MAIN_ONLY_SITE_HEALTH_20261018":"37",
                     "MPW_ZOMOROD_QUALITY_REVIEW_MAIN_ONLY_20261018":"49",
                     "MPW_ZOMOROD_MANAGEMENT_INTELLIGENCE_MAIN_ONLY_20261018":"58",
                     "MPW_PRIVATE_EVOLUTION_MAIN_ONLY_20261018":"*",
                     "MPW_77_MODULES_MAIN_ONLY_20261018":"43"}
            cron="\n".join(f"{min} * * * * /bin/true # {mark}" for mark,min in markers.items())
            with patch.object(robots,"EVO",root/"evolution_runtime_20261018"),patch.object(robots,"PRIVATE",root):
                out=robots.agent_robot(cron)
                self.assertEqual(out["status"],"ok")
                self.assertEqual(out["legacy_modules_active_capabilities"],77)
                self.assertGreaterEqual(out["legacy_module_functional_contracts"],14)
                bad=robots.agent_robot(cron.replace("43 * * * *","41 * * * *"))
                self.assertEqual(bad["status"],"warning")
                self.assertIn("MPW_77_MODULES_MAIN_ONLY_20261018",bad["schedule_mismatches"])

    def test_report_writes_only_private_files(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);root.chmod(0o700)
            with patch.object(robots,"EVO",root):
                robots.atomic(root/"report.json",{"tenant":"mojplaywin-main","status":"ok"})
                self.assertEqual((root/"report.json").stat().st_mode & 0o077,0)
                with self.assertRaisesRegex(RuntimeError,"ROBOT_OUTPUT_NOT_PRIVATE"):
                    robots.atomic(root/"subfolder/report.json",{"tenant":"mojplaywin-main"})

if __name__=="__main__":
    unittest.main()
