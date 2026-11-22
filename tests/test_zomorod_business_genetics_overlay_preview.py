#!/usr/bin/env python3
"""Offline regression checks for additive Zomorod PHP merge. No production access."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "zomorod_business_genetics_overlay_preview.py"
spec = importlib.util.spec_from_file_location("business_overlay", PATH)
assert spec and spec.loader
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)
PROPOSED = (ROOT / "content" / "zomorod-business" / "app.php").read_text(encoding="utf-8")

# Synthetic legacy shape contains the six required anchors, and a host-only
# feature intentionally absent from the GitHub proposed branch.
LEGACY = """<?php
declare(strict_types=1);
const HOST_ONLY_EXTENSION = 'preserve-me-unchanged';
$nav=['projects'=>'پروژه‌ها','mojplaywin'=>'پایش MojPlayWin'];
if($action==='none'){
        } elseif($action==='project'){
    $title=req('title');
            $db->prepare('INSERT INTO projects(title,owner,state,budget) VALUES(?,?,?,?)');
        } elseif($action==='mpw_check'){
}
if($page==='dashboard'){
    echo 'HOST_SITE_CUSTOM_DASHBOARD_FEATURE';
    } elseif($page==='mojplaywin'){
    } elseif($page==='projects'){
        if(role()!=='viewer'){echo '<section><h2>افزودن پروژه</h2>';formBegin('project');}
}
"""


class GeneticsOverlayContract(unittest.TestCase):
    def test_synthetic_host_is_preserved_byte_exact_after_reverse(self):
        candidate, edits, reconstructed = overlay.apply(LEGACY, PROPOSED)
        self.assertEqual(reconstructed, LEGACY)
        self.assertEqual(len(edits), 6)
        self.assertIn("HOST_ONLY_EXTENSION = 'preserve-me-unchanged'", candidate)
        self.assertIn("HOST_SITE_CUSTOM_DASHBOARD_FEATURE", candidate)
        self.assertEqual(candidate.count("genetics_project_register"), 1)
        self.assertEqual(candidate.count("genetics_center'=>"), 1)
        self.assertEqual(candidate.count("genetics-center.php"), 1)
        self.assertIn("BEGIN IMMEDIATE TRANSACTION", candidate)
        self.assertIn("if(role()!=='admin')", candidate)
        self.assertIn("str_starts_with(trim($title)", candidate)
        php = shutil.which("php")
        if php:
            result = subprocess.run(
                [php, "-l"], input=candidate.encode("utf-8"),
                capture_output=True, timeout=12,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))

    def test_refuse_ambiguous_anchor_in_host_variant(self):
        corrupt = LEGACY + "\n$duplicate=['projects'=>'پروژه‌ها','mojplaywin'];\n"
        with self.assertRaises(SystemExit):
            overlay.apply(corrupt, PROPOSED)

    def test_refuse_partially_installed_genetics_module(self):
        tampered = LEGACY + "\n// genetics_project_register\n"
        with self.assertRaises(SystemExit):
            overlay.apply(tampered, PROPOSED)

    def test_character_subsequence_guard_handles_middle_insertion(self):
        self.assertTrue(overlay.is_subsequence("abc", "a123b456c"))
        self.assertFalse(overlay.is_subsequence("abc", "bca"))


if __name__ == "__main__":
    unittest.main()
