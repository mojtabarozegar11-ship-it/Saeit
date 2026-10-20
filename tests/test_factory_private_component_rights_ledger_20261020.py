"""Verify private evidence append-only, hash binding and no fake sales approval."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "scripts/factory_private_component_rights_ledger_20261020.py"
spec = importlib.util.spec_from_file_location("componentrights", str(p))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
src = ROOT / "scripts/factory_commercial_evidence_readonly_20261020.py"
spec = importlib.util.spec_from_file_location("factory_commercial_evidence_readonly_20261020", str(src))
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
import sys
sys.modules["factory_commercial_evidence_readonly_20261020"] = a


class EvidenceLedgers(unittest.TestCase):
    def test_write_once_mode_and_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "private.json"
            self.assertEqual(m.write_once(path, b"safe"), "created")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(m.write_once(path, b"safe"), "existing_verified")
            with self.assertRaisesRegex(ValueError, "PRIVATE_EVIDENCE_CONFLICT"):
                m.write_once(path, b"fake signed")

    def test_five_cpanel_old_claimants_corrected_without_rewriting_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            base = home / ".private/zomorod-business/rights-evidence"
            base.mkdir(parents=True)
            for n in range(5):
                digest = ("%064x" % (n + 1))
                folder = base / digest
                folder.mkdir()
                old = {
                    "schema": "saeit.factory.cpanel-private-rights-register.v1",
                    "recipe": "p" + str(n),
                    "original_archive_sha256": digest,
                    "commercial_distribution_allowed": False,
                    "claimant_chain_of_title_verified": False,
                    "proposed_claimant": "Zomorod Melal Agro-Industry Co. (LLC)",
                    "asset_count": 97,
                }
                (folder / "previous.rights.json").write_text(json.dumps(old))
            result = m.cpanel_legal_addenda(home)
            self.assertEqual(result["created"], 5)
            self.assertEqual(m.cpanel_legal_addenda(home)["existing_verified"], 5)
            for folder in base.iterdir():
                self.assertIn("Zomorod Melal", (folder / "previous.rights.json").read_text())
                new = list(folder.glob("personal_owner_context.*.v2.private.json"))
                self.assertEqual(len(new), 1)
                doc = json.loads(new[0].read_text())
                self.assertTrue(doc["historical_proposed_claimant_company_not_verified_as_owner"])
                self.assertEqual(doc["owner_personal_rights_declared_professional_name"], "مجتبی روزگار")
                self.assertFalse(doc["commercial_release_allowed"])
                self.assertEqual(new[0].stat().st_mode & 0o777, 0o600)

    def test_tamper_with_old_record_prevents_fictitious_clearance(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            base = home / ".private/zomorod-business/rights-evidence"
            base.mkdir(parents=True)
            for n in range(5):
                folder = base / ("%064x" % (n + 1))
                folder.mkdir()
                d = {
                    "schema": "saeit.factory.cpanel-private-rights-register.v1",
                    "original_archive_sha256": folder.name,
                    "commercial_distribution_allowed": False,
                    "claimant_chain_of_title_verified": n != 0,
                    "asset_count": 97,
                }
                (folder / "source.rights.json").write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError, "HISTORICAL_RIGHTS_RECORD_MISMATCH"):
                m.cpanel_legal_addenda(home)


if __name__ == "__main__":
    unittest.main()
