"""Tests for source-backed separate performance charts for added Zomorod agents."""
import json
import tempfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest import TestCase
from command_center.mpw_extra_quality_agent_charts import extra_review_charts

class QualityAndProductRealChartTests(TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.root.chmod(0o700)
        (self.root/"quality_reviews").mkdir(mode=0o700)
        (self.root/"v91_product_policy_audits").mkdir(mode=0o700)
        self.now=datetime(2026,10,18,7,tzinfo=timezone.utc)

    def tearDown(self):self.tmp.cleanup()

    def write(self,folder,name,obj):
        p=self.root/folder/(name+".json")
        p.write_text(json.dumps(obj),encoding="utf8")
        p.chmod(0o600)

    def test_reports_two_real_audits_without_claiming_publication(self):
        self.write("quality_reviews","draft1",{
            "tenant":"mojplaywin-main",
            "reviewed_utc":"2026-10-18T06:00:00Z",
            "status":"needs_editorial_revision","quality_score":72
        })
        self.write("v91_product_policy_audits","draft1",{
            "tenant":"mojplaywin-main",
            "reviewed_utc":"2026-10-18T06:15:00Z",
            "workbook_gate":{"allowed":False},"auto_publish":False,"sale_ready":False,
        })
        rows=extra_review_charts(now=self.now,state=self.root)
        self.assertEqual(len(rows),2)
        data={row["id"]:row for row in rows}
        self.assertEqual(data["scientific_quality_v11"]["completed"],1)
        self.assertEqual(data["scientific_quality_v11"]["warning_count"],1)
        self.assertEqual(data["product_policy_v91"]["completed"],1)
        self.assertEqual(data["product_policy_v91"]["warning_count"],1)
        self.assertTrue(all(len(x["series"])==14 for x in rows))
        self.assertTrue(all(x["status"]=="active_private" for x in rows))

    def test_wrong_tenant_old_files_or_invalid_data_do_not_count(self):
        self.write("quality_reviews","alien",{
            "tenant":"zomorodmelal","reviewed_utc":"2026-10-18T06:00:00Z",
            "status":"needs_editorial_revision"})
        self.write("v91_product_policy_audits","old",{
            "tenant":"mojplaywin-main","reviewed_utc":"2026-06-18T06:15:00Z",
            "workbook_gate":{"allowed":False},"auto_publish":False,"sale_ready":False,
        })
        rows=extra_review_charts(now=self.now,state=self.root)
        self.assertTrue(all(x["completed"]==0 for x in rows))
        self.assertTrue(all(x["history_available"] is False for x in rows))
        self.assertTrue(all(x["warning_count"]==0 for x in rows))
