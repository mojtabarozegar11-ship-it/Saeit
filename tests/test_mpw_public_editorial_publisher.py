"""Tests ensuring static publication never overwrites shared site or unreviewed content."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from mpw_v91_port import page_content_factory as f
from mpw_v91_port import public_editorial_publisher as p

def reviewer(*args):
    return "candidate_ready_for_human_review"

def fixture(root):
    f.tick(root,"2026-10-18T14:00:00+00:00",reviewer)
    (root/"gen65_operational_report.json").write_text(json.dumps({
        "tenant":p.TENANT, "status":"gen65_operational_private",
        "active_private_generation":65,"existing_public_master_generation":64}))

class EditorialPublicationTests(unittest.TestCase):
    def test_exact_two_original_reviewed_articles_become_safe_html(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as st:
            root=Path(td);stage=Path(st);fixture(root)
            outcome=p.render_to_staging(root,stage)
            self.assertEqual(outcome["generated_articles"],2)
            self.assertEqual(len(outcome["article_slugs"]),2)
            articles=list((stage/"agents").glob("*/index.html"))
            self.assertEqual(len(articles),2)
            body=articles[0].read_text()
            self.assertIn("MojPlayWin",body)
            self.assertIn('rel="canonical"',body)
            self.assertIn("Educational material",body)
            self.assertIn('/index.html"',body)
            self.assertIn('<link rel="canonical" href="https://mojplaywin.com/mpw-standalone-guides/agents/',body)
            self.assertNotIn('href="/mpw-standalone-guides/agents/ai-evaluation-before-deployment/"',body)
            index=(stage/"index.html").read_text()
            self.assertIn('href="/mpw-standalone-guides/agents/ai-evaluation-before-deployment/index.html"',index)
            self.assertIn('href="/mpw-standalone-guides/agents/documenting-ai-assisted-decisions/index.html"',index)
            self.assertIn('href="/mpw-standalone-guides/index.html"',index)
            self.assertIn("href=",body)
            self.assertNotIn("zomorodmelal.ir",body.lower())
            self.assertNotIn("<script",body)
            self.assertTrue((stage/"index.html").is_file())
            self.assertTrue((stage/"agents/index.html").is_file())
            self.assertTrue((stage/"knowledge/index.html").is_file())

    def test_same_content_yields_identical_files(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as s1, tempfile.TemporaryDirectory() as s2:
            root=Path(td);fixture(root)
            p.render_to_staging(root,Path(s1))
            p.render_to_staging(root,Path(s2))
            for file in Path(s1).rglob("*"):
                if file.is_file():
                    self.assertEqual(file.read_bytes(),(Path(s2)/file.relative_to(s1)).read_bytes())

    def test_tampered_body_rejected(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as st:
            root=Path(td);fixture(root)
            source=next((root/"page_content_20261018/drafts").glob("*.json"))
            obj=json.loads(source.read_text());obj["body_markdown"]+=" Free guaranteed profits!"
            source.write_text(json.dumps(obj))
            with self.assertRaisesRegex(RuntimeError,"unverified_text_or_source"):
                p.render_to_staging(root,Path(st))

    def test_changed_gen65_status_rejected(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as st:
            root=Path(td);fixture(root)
            (root/"gen65_operational_report.json").write_text(json.dumps({
                "tenant":p.TENANT, "status":"disabled", "active_private_generation":65,
                "existing_public_master_generation":64}))
            with self.assertRaisesRegex(RuntimeError,"gen65_operational_proof_missing"):
                p.render_to_staging(root,Path(st))

    def test_extra_unexpected_private_draft_stops(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as st:
            root=Path(td);fixture(root)
            (root/"page_content_20261018/drafts/unknown.json").write_text("{}")
            with self.assertRaisesRegex(RuntimeError,"foreign_editorial_file"):
                p.render_to_staging(root,Path(st))

    def test_only_expected_publication_canonical_and_safe_markup(self):
        with self.assertRaisesRegex(RuntimeError,"untrusted_public_canonical"):
            p._frame("a","b","https://zomorodmelal.ir/blog/a/","desc")
        with self.assertRaisesRegex(RuntimeError,"unexpected_content_markup"):
            p._render_markdown("# Title\n<script>alert('x')</script>")

    def test_all_sections_and_article_count_cap(self):
        with tempfile.TemporaryDirectory() as td:
            rows=[f.build(brief,"2026-10-18T12:00:00+00:00") for brief in f.BRIEFS]
            files=p.make_files(rows)
            self.assertEqual(len([k for k in files if k.endswith("/index.html") and k.count("/")==2]),8)
            self.assertIn("agents/index.html",files)
            self.assertIn("studio/index.html",files)
            self.assertIn("research/index.html",files)
            self.assertIn("knowledge/index.html",files)
            self.assertFalse(any("farnaz" in key or "mojtaba" in key for key in files))
            self.assertRaisesRegex(RuntimeError,"article_limit",p.make_files,rows+rows[0:1])

    def test_shared_or_foreign_directory_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as td:
            docroot=Path(td)
            (docroot/"passenger_wsgi.py").write_text("pass")
            (docroot/".htaccess").write_text("pass")
            target=docroot/"mpw-standalone-guides"
            target.mkdir()
            (target/p.OWNER).write_text(json.dumps({
                "tenant":p.TENANT,
                "scope":"mojplaywin-main-static-standalone-guides-only",
                "content_fingerprints":{}
            }))
            (target/"arcade-lab").mkdir()
            with patch.object(p,"DOCROOT",docroot):
                with self.assertRaisesRegex(RuntimeError,"unexpected_top_level"):
                    p.verify_public_target(docroot,target)
            self.assertTrue((target/"arcade-lab").is_dir())

    def test_nonowned_standalone_target_is_denied(self):
        with tempfile.TemporaryDirectory() as td:
            docroot=Path(td)
            (docroot/"passenger_wsgi.py").write_text("pass")
            (docroot/".htaccess").write_text("pass")
            target=docroot/"mpw-standalone-guides"
            target.mkdir()
            (target/"index.html").write_text("not our page")
            with patch.object(p,"DOCROOT",docroot):
                with self.assertRaisesRegex(RuntimeError,"unsafe_editorial_input"):
                    p.verify_public_target(docroot,target)
            self.assertEqual((target/"index.html").read_text(),"not our page")

    def test_private_manifest_and_unowned_docroot_refused(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(RuntimeError,"documentroot_attestation_failed"):
                p.verify_public_target(Path(td),Path(td)/"mpw-standalone-guides")

if __name__=="__main__":
    unittest.main()
