"""Release quality must be fully evidenced; not a 99.5 rounded average."""
import json
from copy import deepcopy
from pathlib import Path
import unittest

from scripts.mojplaywin_release_100_gate import MANDATORY, validate


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "quality" / "mojplaywin-acceptance-100.json"


class MojPlayWinRelease100Tests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(SOURCE.read_text(encoding="utf-8"))

    def test_all_nineteen_quality_sections_are_required(self):
        self.assertEqual(len(MANDATORY), 19)
        self.assertEqual({x["id"] for x in self.manifest["gates"]}, MANDATORY)
        for must in ("crypto_payment_integrity", "products_inventory",
                     "protected_subsites", "approved_orbital_design", "django_admin",
                     "agents_runtime", "backup_and_rollback", "performance_mobile"):
            self.assertIn(must, MANDATORY)

    def test_current_draft_is_rejected_when_real_evidence_is_missing(self):
        result = validate(self.manifest)
        self.assertFalse(result["release_authorized_by_checklist"])
        self.assertEqual(result["accepted_gates"], 0)
        self.assertEqual(result["required_gates"], 19)
        self.assertEqual(len(result["incomplete_gates"]), 19)

    def fully_verified_fixture(self):
        data = deepcopy(self.manifest)
        for x in data["gates"]:
            manual = x["id"] in {"approved_orbital_design", "approved_release"}
            x["status"] = "passed"
            x["verified_at_utc"] = "2026-10-17T12:10:00+00:00"
            x["evidence"] = [{
                "kind": "manual_owner" if manual else "automated",
                "url": "https://github.com/example/project/actions/runs/123456",
                "summary": "Synthetic test-only evidence for the quality validator",
                "result": "pass",
            }]
        return data

    def test_all_quality_sections_must_pass_individually(self):
        fixture = self.fully_verified_fixture()
        self.assertTrue(validate(fixture)["release_authorized_by_checklist"])
        for x in fixture["gates"]:
            changed = deepcopy(fixture)
            target = next(v for v in changed["gates"] if v["id"] == x["id"])
            target["status"] = "failed"
            with self.subTest(gate=x["id"]):
                result = validate(changed)
                self.assertFalse(result["release_authorized_by_checklist"])
                self.assertIn(x["id"], result["incomplete_gates"])

    def test_missing_or_self_attested_proof_is_insufficient(self):
        for kind, url in (("automated", "http://example.com"),
                          ("manual_owner", "https://example.com/test"),
                          ("automated", "https://user:secret@example.com/other"),
                          ("automated", "")):
            fixture = self.fully_verified_fixture()
            item = next(v for v in fixture["gates"] if v["id"] == "products_inventory")
            item["evidence"] = [{"kind": kind, "url": url,
                                "summary": "Sample result text for mandatory verification",
                                "result": "pass"}]
            with self.subTest(kind=kind, url=url):
                self.assertFalse(validate(fixture)["release_authorized_by_checklist"])

    def test_no_fake_owner_approval_or_missing_timestamp(self):
        fixture = self.fully_verified_fixture()
        approval = next(v for v in fixture["gates"] if v["id"] == "approved_release")
        approval["evidence"][0]["kind"] = "automated"
        self.assertFalse(validate(fixture)["release_authorized_by_checklist"])
        fixture = self.fully_verified_fixture()
        fixture["gates"][0]["verified_at_utc"] = "2026-10-17"
        self.assertFalse(validate(fixture)["release_authorized_by_checklist"])

    def test_missing_gate_duplicate_or_extra_gate_is_rejected(self):
        fixture = self.fully_verified_fixture()
        fixture["gates"].pop()
        self.assertFalse(validate(fixture)["release_authorized_by_checklist"])
        fixture = self.fully_verified_fixture()
        fixture["gates"].append(deepcopy(fixture["gates"][0]))
        self.assertFalse(validate(fixture)["release_authorized_by_checklist"])


if __name__ == "__main__":
    unittest.main()
