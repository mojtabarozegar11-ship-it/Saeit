"""Regression for private Zomorod-derived quality reviewer and staff chart."""
import hashlib,json,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from scripts.mpw_review_private_drafts_with_zomorod_quality import (
    policy_from_source, assess, review_private
)
from command_center.mpw_quality_review_charts import quality_review_chart_rows

class MojPlayWinPrivateScientificQualityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.base=Path(self.tmp.name)
        self.ref=self.base/"ref"
        self.ref.mkdir(mode=0o700)
        self.state=self.base/"private"
        self.state.mkdir(mode=0o700)
        for name in ("processed","drafts"):
            (self.state/name).mkdir(mode=0o700)
        sources={
            "core/knowledge_quality.py":(
                "QUALITY_GATES=('source_provenance','publication_control')\n"
                "SEO_REQUIREMENTS=('search_intent','title_meta','headings','internal_links','freshness_signal')\n"
                "def quality_contract(): return {'quality_gates':QUALITY_GATES}\n"),
            "core/newsletter_engine.py":"MIN_AUTO_PUBLISH_SCORE=90\n",
        }
        checks={}
        for rel,contents in sources.items():
            p=self.ref/"reference"/rel
            p.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            p.write_text(contents)
            checks[rel]=hashlib.sha256(contents.encode()).hexdigest()
        (self.ref/"manifest.json").write_text(json.dumps({"files":checks}))

    def tearDown(self):
        self.tmp.cleanup()

    def test_quality_policy_is_parsed_not_executed(self):
        p=policy_from_source(self.ref)
        self.assertEqual(p["source_newsroom_threshold"],90)
        self.assertIn("source_provenance",p["quality_gates"])

    def test_private_draft_is_reviewed_but_not_published(self):
        original={"tenant":"mojplaywin-main","review_only":True,"kind":"research_digest"}
        raw=json.dumps(original).encode()
        key=hashlib.sha256(raw).hexdigest()[:24]
        (self.state/"processed"/"test.json").write_bytes(raw)
        (self.state/"drafts"/(key+".json")).write_text(json.dumps({
            "draft":{"tenant":"mojplaywin-main","review_required":True,
                     "published":False,"title":"عنوان آزمایشی",
                     "summary":"خلاصه آزمایشی","body":"متن ساختگی",
                     "sources":["https://example.org/"]}}))
        result=review_private(self.state,self.ref)
        self.assertEqual(result["actual_private_drafts_scored"],1)
        self.assertEqual(result["quality_review_results"]["needs_editorial_revision"],1)
        evidence=json.loads((self.state/"quality_reviews"/(key+".json")).read_text())
        self.assertFalse(evidence["checks"]["body_substantial"])
        self.assertTrue(evidence["never_auto_publish"])
        self.assertEqual(evidence["tenant"],"mojplaywin-main")
        rows=quality_review_chart_rows(datetime.now(timezone.utc),self.state/"quality_reviews")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["completed"],1)
        self.assertEqual(rows[0]["needs_revision"],1)
        self.assertEqual(rows[0]["series"][-1],1)

    def test_fails_closed_when_source_changes(self):
        (self.ref/"reference/core/knowledge_quality.py").write_text("print('hijacked')\n")
        with self.assertRaises(RuntimeError):
            policy_from_source(self.ref)

    def test_foreign_site_records_are_not_scored(self):
        self.assertEqual(assess({"draft":{"tenant":"zomorodmelal","published":False,
           "review_required":True}},policy_from_source(self.ref))["checks"]["tenant_valid"],False)
        self.assertEqual(review_private(self.state,self.ref)["actual_private_drafts_scored"],0)
