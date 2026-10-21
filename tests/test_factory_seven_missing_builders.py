"""Deterministic source-builder and fail-closed specialist QA tests."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SRC=Path(__file__).resolve().parents[1]/"scripts"/"factory_seven_missing_builders.py"
spec=importlib.util.spec_from_file_location("seven_gap_builders",str(SRC))
gap=importlib.util.module_from_spec(spec);spec.loader.exec_module(gap)

class SevenGapTests(unittest.TestCase):
    def test_identity_and_no_false_professional_clearance(self):
        self.assertEqual(len(gap.FAMILIES),7)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for family in ("F12","F13","F16","F17","F26"):
                result=gap.create(root,family)
                self.assertEqual(result["family_id"],family)
                self.assertFalse(result["independent_quality_1000_passed"])
                self.assertFalse(result["commercial_release_allowed"])
                self.assertFalse(result["public_listing_enabled"])
                self.assertTrue(result["private_archive_sha256"])
                self.assertEqual(gap.create(root,family)["status"],"unchanged_private_candidate")
    def test_training_is_actual_computed_fit(self):
        models=[gap.train_model(i) for i in range(48)]
        self.assertEqual(len({m["id"] for m in models}),48)
        self.assertTrue(all(m["mae"]<0.5 for m in models))
        self.assertEqual(len({tuple(round(w,4) for w in x["weights"]) for x in models}),48)
    def test_levels_reachable_and_distinct(self):
        levels=gap.levels()
        self.assertEqual(len(levels),48)
        self.assertTrue(all(all(x not in item["walls"] for x in [0,1,2,3,4,5,11,17,23,29,35]) for item in levels))
        self.assertEqual(len({tuple(x["walls"]) for x in levels}),48)
    def test_f40_no_fake_mp3(self):
        oldvoice=gap.audio_available;oldff=gap.media_ffmpeg
        try:
            gap.audio_available=lambda:None
            gap.media_ffmpeg=lambda:None
            with tempfile.TemporaryDirectory() as folder:
                result=gap.create(Path(folder),"F40")
                self.assertNotEqual(result["status"],"verified_synthesized_mp3_and_vtt_private_pilot")
                self.assertIn("espeak/espeak-ng voice engine and ffmpeg native MP3 encoder",
                              result["unresolved_native_or_specialist_gates"])
                product=Path(folder)/"engineering-gaps"/"seven-builders"/result["product_id"]
                self.assertFalse(list(product.rglob("*.mp3")))
        finally:
            gap.audio_available=oldvoice;gap.media_ffmpeg=oldff
    def test_f23_native_builder_not_substituted(self):
        with tempfile.TemporaryDirectory() as folder:
            result=gap.create(Path(folder),"F23")
            self.assertTrue(any(x.startswith("existing_50_stage_producer:") for x in result["actual_checks"]))
            self.assertFalse(result["independent_quality_1000_passed"])
            self.assertTrue(result["unresolved_native_or_specialist_gates"])
if __name__=="__main__":unittest.main()
