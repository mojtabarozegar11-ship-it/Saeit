"""Reviewed legacy 0041 intake-only model/admin upgrade to complete commercial chain.

All tests use a temporary fake app tree, never a real host or database.
The exact legacy 0041-era suffixes came from a previously reviewed GitHub
source branch. Any owner modifications in that suffix must fail closed.
"""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import deploy_mojplaywin_moj_prop_backend as installer
from scripts.mojprop_schema_preflight_c83 import (
    LEGACY_BASELINES, check_schema_closure, has_reviewed_legacy_suffix,
)


SOURCE = Path(__file__).resolve().parents[1]
PREFIXES = {
    "core/models.py": "from django.db import models\nclass T(models.Model):\n    pass\n",
    "core/admin.py": (
        "from django.contrib import admin\n"
        "from django.contrib.admin import ModelAdmin\n"
        "class PreservedAdmin: pass\n"
    ),
}
EXPECTED = {
    "core/models.py": ("MojPropRequest", "MojPropOffer", "MojPropDeliveryEvidence"),
    "core/admin.py": (
        "MojPropRequestAdmin", "MojPropOfferAdmin",
        "MojPropDeliveryEvidenceAdmin",
    ),
}


class MojPropLegacyUpgradeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for relative, prefix in PREFIXES.items():
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            snapshot = (SOURCE / LEGACY_BASELINES[relative]).read_text(encoding="utf-8")
            target.write_text(prefix + "\n" + snapshot, encoding="utf-8")
        (self.root / "core/migrations").mkdir(parents=True)

    def test_both_exact_legacy_suffixes_have_reviewed_upgrade_path(self):
        p = check_schema_closure(self.root, SOURCE)
        self.assertEqual(
            p["legacy_upgrade_reviewed"], {"models": True, "admin": True}
        )
        for name in PREFIXES:
            self.assertTrue(has_reviewed_legacy_suffix(self.root, SOURCE, name))

    def test_known_intake_model_and_admin_expand_without_editing_unrelated_prefix(self):
        with patch.object(installer, "ROOT", self.root):
            with contextlib.redirect_stdout(io.StringIO()):
                installer.patch_models(self.root / "core/models.py", SOURCE / "core/models.py")
                installer.patch_admin(self.root / "core/admin.py", SOURCE / "core/admin.py")
        for relative, prefix in PREFIXES.items():
            result = (self.root / relative).read_text(encoding="utf-8")
            self.assertTrue(result.startswith(prefix))
            for class_name in EXPECTED[relative]:
                self.assertEqual(result.count("class " + class_name + "("), 1)
        self.assertEqual(
            check_schema_closure(self.root, SOURCE)["legacy_upgrade_reviewed"],
            {"models": False, "admin": False},
        )

    def test_reviewed_upgrade_is_idempotent(self):
        with patch.object(installer, "ROOT", self.root):
            with contextlib.redirect_stdout(io.StringIO()):
                installer.patch_models(self.root / "core/models.py", SOURCE / "core/models.py")
                installer.patch_admin(self.root / "core/admin.py", SOURCE / "core/admin.py")
            after = [(self.root / name).read_bytes() for name in PREFIXES]
            with contextlib.redirect_stdout(io.StringIO()):
                installer.patch_models(self.root / "core/models.py", SOURCE / "core/models.py")
                installer.patch_admin(self.root / "core/admin.py", SOURCE / "core/admin.py")
        self.assertEqual(after, [(self.root / name).read_bytes() for name in PREFIXES])

    def test_owner_edited_partial_model_or_admin_is_rejected_and_untouched(self):
        for relative in PREFIXES:
            with self.subTest(relative=relative):
                file = self.root / relative
                original = file.read_text(encoding="utf-8")
                file.write_text(original + "\n# owner modification\n", encoding="utf-8")
                before = file.read_bytes()
                with self.assertRaisesRegex(RuntimeError, "partial Moj Prop"):
                    check_schema_closure(self.root, SOURCE)
                self.assertEqual(file.read_bytes(), before)
                file.write_text(original, encoding="utf-8")

    def test_only_staged_snapshots_not_live_modules(self):
        for snap in LEGACY_BASELINES.values():
            rel = Path(snap)
            self.assertIn(rel, installer.ALL_FILES)
            self.assertNotIn(rel, installer.REPLACE_FILES)


if __name__ == "__main__":
    unittest.main()
