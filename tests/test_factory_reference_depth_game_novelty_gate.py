"""Regression proof that old polished games fail new-original-product novelty,
and superficial specialist books fail reference-grade quality assessment.
No test is allowed to grant automatic sales, even on structurally complete input.
"""
import hashlib
import importlib.util
import json
from datetime import date
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
SCRIPT=HERE/"scripts/factory_reference_depth_game_novelty_gate.py"
spec=importlib.util.spec_from_file_location("factory_gate",SCRIPT)
gate=importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

def codes(report):
    return {x["code"] for x in report["blockers"]}

class PremiumProductQA(unittest.TestCase):
    def test_old_clash_of_clans_fails_if_represented_as_brand_new(self):
        """Global 2012 release is an OLD baseline, irrespective of successful code tests."""
        candidate={
            "id":"adversarial-comparator-clash-2012","family":"F14",
            "distribution_claim":"new_original_commercial_product",
            "game":{
                "original_release_year":2012,
                "core_loop_tags":["base_build","resource_collect","troop_train",
                                  "raid_attack","clan_war","upgrade_wait"],
                "independent_comparators":[],
                "original_playtested_mechanics":[],
                "documented_2026_player_need":False,
                "accessible_without_pointer":True
            }
        }
        with tempfile.TemporaryDirectory() as p:
            r=gate.examine(candidate,Path(p))
        self.assertEqual(r["verdict"],"BLOCKED_REWORK_REQUIRED")
        self.assertIn("GAME_OLD_OR_UNPROVEN_NEW_RELEASE",codes(r))
        self.assertIn("GAME_LEGACY_CLONE_MECHANICS",codes(r))
        self.assertIn("GAME_NO_VERIFIABLE_NOVEL_GAMEPLAY",codes(r))
        self.assertFalse(r["professional_game_certified"])
        self.assertFalse(r["commercial_release_authorized"])

    def test_new_release_date_does_not_launder_an_old_cloned_loop(self):
        with tempfile.TemporaryDirectory() as p:
            r=gate.examine({
              "family":"F14","distribution_claim":"new_original_commercial_product",
              "game":{"original_release_year":date.today().year,
                      "core_loop_tags":list(gate.LEGACY_LOOP),
                      "independent_comparators":[{"identifier":"a"},{"identifier":"b"},{"identifier":"c"}],
                      "original_playtested_mechanics":[]}
            },Path(p))
        self.assertNotIn("GAME_OLD_OR_UNPROVEN_NEW_RELEASE",codes(r))
        self.assertIn("GAME_LEGACY_CLONE_MECHANICS",codes(r))
        self.assertIn("GAME_NO_VERIFIABLE_NOVEL_GAMEPLAY",codes(r))
        self.assertEqual(r["verdict"],"BLOCKED_REWORK_REQUIRED")

    def test_weak_technical_textbook_fails_reference_depth(self):
        data={"family":"F01","book":{
            "type":"medical","parts":["Introduction"],
            "chapters":[{"subject":"Cardiac Surgery", "citations":[]}],
            "literature_reviewed_through_year":2018
        }}
        with tempfile.TemporaryDirectory() as p:
            r=gate.examine(data,Path(p))
        for defect in ("BOOK_INSUFFICIENT_SYSTEMATIC_COVERAGE",
                       "BOOK_REFERENCE_DEPTH_NOT_DEMONSTRATED",
                       "BOOK_LITERATURE_NOT_CURRENT",
                       "BOOK_CLINICAL_HARM_REVIEW_MISSING",
                       "BOOK_COMPILATION_NOT_EXPERT_SYNTHESIS"):
            self.assertIn(defect,codes(r))
        self.assertFalse(r["doctoral_grade_certified"])

    def test_structural_excellence_cannot_fake_expert_authenticity(self):
        chapters=[{"subject":"Specialist Topic "+str(i),
                   "citations":["Study A","Study B","Study C"],
                   "methods_and_limits":"Methodological limitations, uncertainty and competing explanations reviewed."}
                  for i in range(22)]
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            evidence={}
            for name in gate.EVIDENCE_CRITICAL["F01"]:
                filepath=root/(name+".txt")
                filepath.write_text("Structured evidence for "+name+" (NOT authenticated expert approval).")
                evidence[name]={"path":filepath.name,"sha256":hashlib.sha256(filepath.read_bytes()).hexdigest()}
            c={"family":"F01","id":"high-depth-but-unverified","evidence":evidence,
               "book":{"type":"engineering","parts":["I","II","III","IV","V","VI"],
                       "chapters":chapters,"literature_reviewed_through_year":date.today().year,
                       "original_analysis_per_chapter":True}}
            r=gate.examine(c,root)
            self.assertNotIn("BOOK_REFERENCE_DEPTH_NOT_DEMONSTRATED",codes(r))
            self.assertFalse(any(x.startswith("EVIDENCE_MISSING") for x in codes(r)))
            self.assertIn("INDEPENDENT_HUMAN_AUTHENTICATION_PENDING",codes(r))
            self.assertFalse(r["publish_allowed"])
            self.assertFalse(r["doctoral_grade_certified"])
            # Invalidate bytes without changing SHA: must now catch tampering.
            (root/"claim_to_reference_matrix.txt").write_text("tampered")
            changed=gate.examine(c,root)
            self.assertIn("EVIDENCE_MISSING_OR_BAD_HASH:claim_to_reference_matrix",codes(changed))

    def test_generic_all_40_families_never_mistaken_for_quality_pass(self):
        with tempfile.TemporaryDirectory() as p:
            root=Path(p)
            for number in range(1,41):
                family="F%02d"%number
                r=gate.examine({"family":family},root)
                self.assertEqual(r["family"],family)
                self.assertFalse(r["commercial_release_authorized"])
                self.assertFalse(r["publish_allowed"])
                self.assertEqual(r["verdict"],"BLOCKED_REWORK_REQUIRED")
                if family not in ("F01","F14","F28"):
                    self.assertIn("FAMILY_SPECIALIST_RUBRIC_NOT_IMPLEMENTED",codes(r))

    def test_adversarial_manifest_cannot_self_approve_even_with_boolean_flags(self):
        with tempfile.TemporaryDirectory() as p:
            r=gate.examine({
                "family":"F14","release_status":"commercially_approved",
                "attested_independent_human_quality_review":True,
                "attested_authentic_scientific_or_game_design_review":True,
                "attested_owner_approval_for_exact_release":True,
                "game":{"original_release_year":date.today().year}
            },Path(p))
            self.assertIn("SELF_DECLARED_APPROVAL_NOT_EVIDENCE",codes(r))
            self.assertFalse(r["commercial_release_authorized"])

    def test_cli_does_not_return_success_for_commercial_release(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            manifest=root/"candidate.json"
            manifest.write_text(json.dumps({"family":"F14","game":{"original_release_year":2012}}))
            out=root/"result.json"
            process=subprocess.run([sys.executable,str(SCRIPT),
                                    "--manifest",str(manifest),
                                    "--evidence-root",str(root),
                                    "--report",str(out),
                                    "--enforce-commercial"],capture_output=True,text=True,timeout=10)
            self.assertEqual(process.returncode,2,process.stderr)
            self.assertTrue(out.exists())
            self.assertFalse(json.loads(out.read_text())["commercial_release_authorized"])

if __name__=="__main__":
    unittest.main()
