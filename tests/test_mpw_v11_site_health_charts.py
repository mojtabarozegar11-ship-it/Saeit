"""Verified V11 site health charts, not estimated and never mixed with factory."""
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import TestCase

from command_center.mpw_v11_site_agent_charts import AUDIT_AGENTS,site_agent_chart_rows

class TestMojPlayWinElevenMonitors(TestCase):
    def setUp(self):
        self.base=tempfile.TemporaryDirectory()
        self.root=Path(self.base.name)
        self.root.chmod(0o700)
        self.now=datetime(2026,10,18,5,30,tzinfo=timezone.utc)

    def tearDown(self):
        self.base.cleanup()

    def _scan(self, day,fail=None):
        timestamp=(self.now-timedelta(days=day)).isoformat()
        return {"tenant":"mojplaywin-main","total_agents":11,"observed_utc":timestamp,
                "runs":[{"code":code,"status":"error" if code==fail else "ok","http":0 if code==fail else 200}
                        for code,_,_ in AUDIT_AGENTS]}
    def _write(self,*records):
        (self.root/"history.jsonl").write_text("\n".join(json.dumps(r) for r in records)+"\n",encoding="utf8")
        (self.root/"history.jsonl").chmod(0o600)

    def test_only_real_private_confirmed_http_checks_are_charted(self):
        self._write(self._scan(0),self._scan(1,fail="weather"))
        agents=site_agent_chart_rows(self.now,self.root)
        self.assertEqual(len(agents),11)
        by={x["id"]:x for x in agents}
        self.assertEqual(by["site_v11_master"]["completed"],2)
        self.assertEqual(by["site_v11_weather"]["completed"],1)
        self.assertEqual(by["site_v11_weather"]["error_count"],1)
        self.assertEqual(by["site_v11_master"]["status"],"ok")
        self.assertEqual(len(by["site_v11_master"]["series"]),14)
        self.assertTrue(all(x["metric_kind"]=="site_health_checks" for x in agents))
        self.assertEqual({x["id"] for x in agents},{"site_v11_"+x[0] for x in AUDIT_AGENTS})

    def test_missing_private_file_is_not_reported_as_success(self):
        rows=site_agent_chart_rows(self.now,self.root)
        self.assertEqual(len(rows),11)
        self.assertTrue(all(r["history_available"] is False for r in rows))
        self.assertTrue(all(r["status"]=="unavailable" for r in rows))

    def test_duplicate_real_record_not_double_counted(self):
        sample=self._scan(0)
        self._write(sample,sample)
        rows=site_agent_chart_rows(self.now,self.root)
        self.assertTrue(all(r["completed"]==1 for r in rows))

    def test_older_than_14_days_is_not_fabricated_in_recent_chart(self):
        self._write(self._scan(20))
        rows=site_agent_chart_rows(self.now,self.root)
        self.assertTrue(all(r["completed"]==0 and not r["history_available"] for r in rows))

    def test_other_tenant_ignored(self):
        row=self._scan(0);row["tenant"]="zomorodmelal"
        self._write(row)
        rows=site_agent_chart_rows(self.now,self.root)
        self.assertTrue(all(r["completed"]==0 for r in rows))
