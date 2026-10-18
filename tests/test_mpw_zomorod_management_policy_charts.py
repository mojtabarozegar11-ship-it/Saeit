"""Management/economic agents must use genuine private evidence and never spoof runs."""
import json
import tempfile
from pathlib import Path
from datetime import datetime,timezone
from django.test import SimpleTestCase
from command_center.mpw_zomorod_management_charts import rows

class PrivateZomorodPolicyAgentDashboardTests(SimpleTestCase):
    def test_does_not_claim_two_agents_running_with_no_source_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            root.chmod(0o700)
            reports=rows(datetime(2026,10,18,7,tzinfo=timezone.utc),root)
        self.assertEqual(len(reports),2)
        self.assertEqual({a["id"] for a in reports},
            {"company_activity_intelligence","economic_master_policy"})
        self.assertTrue(all(a["status"]=="unavailable" for a in reports))
        self.assertTrue(all(a["history_available"] is False and a["series"] is None for a in reports))

    def test_only_private_tenant_evidence_is_counted(self):
        instant=datetime(2026,10,18,7,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            root.chmod(0o700)
            for role,filename in (("company_activity_intelligence","latest_company_operations.json"),
                                  ("economic_master_policy","latest_economic_policy.json")):
                (root/filename).write_text(json.dumps({
                    "tenant":"mojplaywin-main",
                    "observed_utc":"2026-10-18T06:45:00Z",
                    "report":{"id":role,"published":False}
                }),encoding="utf8")
            reports=rows(instant,root)
        self.assertTrue(all(x["status"]=="active_private" for x in reports))
        self.assertTrue(all(x["completed"]==1 for x in reports))
        self.assertTrue(all(x["history_available"] is False for x in reports))
        self.assertTrue(all(x["series"] is None for x in reports))

    def test_other_tenants_and_publication_are_never_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);root.chmod(0o700)
            (root/"latest_company_operations.json").write_text(json.dumps({
                "tenant":"zomorodmelal",
                "observed_utc":"2026-10-18T06:45:00Z",
                "report":{"id":"company_activity_intelligence","published":False}
            }))
            (root/"latest_economic_policy.json").write_text(json.dumps({
                "tenant":"mojplaywin-main",
                "observed_utc":"2026-10-18T06:45:00Z",
                "report":{"id":"economic_master_policy","published":True}
            }))
            results=rows(datetime(2026,10,18,7,tzinfo=timezone.utc),root)
        self.assertTrue(all(x["status"]=="unavailable" for x in results))
