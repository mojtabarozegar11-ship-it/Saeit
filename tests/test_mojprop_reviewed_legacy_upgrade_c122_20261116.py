"""Offline reviewed legacy intake-only → full Moj Prop model/admin upgrade.

The test tree is temporary. No production files, DB connection, payment,
email, network or migration is executed.
"""
from __future__ import annotations

import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import deploy_mojplaywin_moj_prop_backend as installer
from scripts.mojprop_schema_preflight_c83 import (
    ADMINS, LEGACY_BASELINES, MIGRATIONS, MODELS, MODULES,
    check_schema_closure, has_reviewed_legacy_suffix,
)

SOURCE = Path(__file__).resolve().parents[1]
PREFIXES = {
    "core/models.py": (
        "from django.db import models\n"
        "class T(models.Model):\n    pass\n"
    ),
    "core/admin.py": (
        "from django.contrib import admin\n"
        "from django.contrib.admin import ModelAdmin\n"
        "class PreservedAdmin:\n    pass\n"
    ),
}


class ReviewedLegacyUpgradeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.live = Path(tmp.name)
        (self.live / "core/migrations").mkdir(parents=True)
        self.stage = self.live / "reviewed_release_stage"
        for relative in (
            "core/models.py", "core/admin.py", "config/urls.py", "config/settings.py",
            *MODULES,
            *LEGACY_BASELINES.values(),
            *(f"core/migrations/{name}.py" for name in MIGRATIONS),
        ):
            target = self.stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SOURCE / relative, target)
        for relative, prefix in PREFIXES.items():
            path = self.live / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            fixture = (SOURCE / LEGACY_BASELINES[relative]).read_text(encoding="utf-8")
            path.write_text(prefix + "\n" + fixture, encoding="utf-8")
        root_patch = patch.object(installer, "ROOT", self.live)
        root_patch.start()
        self.addCleanup(root_patch.stop)

    def patch_both(self):
        with contextlib.redirect_stdout(io.StringIO()):
            installer.patch_models(self.live / "core/models.py", SOURCE / "core/models.py")
            installer.patch_admin(self.live / "core/admin.py", SOURCE / "core/admin.py")

    def test_exact_legacy_model_suffix_is_recognized(self):
        self.assertTrue(has_reviewed_legacy_suffix(self.live, SOURCE, "core/models.py"))

    def test_exact_legacy_admin_suffix_is_recognized(self):
        self.assertTrue(has_reviewed_legacy_suffix(self.live, SOURCE, "core/admin.py"))

    def test_reviewed_intake_only_source_passes_preflight(self):
        result = check_schema_closure(self.live, self.stage)
        self.assertEqual(result["source_chain"], list(MIGRATIONS))
        self.assertFalse(result["live_db_restored"])

    def test_model_upgrade_preserves_unrelated_prefix(self):
        self.patch_both()
        source = (self.live / "core/models.py").read_text(encoding="utf-8")
        self.assertTrue(source.startswith(PREFIXES["core/models.py"]))
        for name in MODELS:
            self.assertEqual(source.count("class " + name + "("), 1)

    def test_admin_upgrade_preserves_unrelated_prefix(self):
        self.patch_both()
        source = (self.live / "core/admin.py").read_text(encoding="utf-8")
        self.assertTrue(source.startswith(PREFIXES["core/admin.py"]))
        for name in ADMINS:
            self.assertEqual(source.count("class " + name + "("), 1)

    def test_upgrade_is_idempotent(self):
        self.patch_both()
        first = [(self.live / relative).read_bytes() for relative in PREFIXES]
        self.patch_both()
        self.assertEqual(first, [(self.live / relative).read_bytes() for relative in PREFIXES])

    def test_expanded_sources_pass_current_main_closure(self):
        self.patch_both()
        result = check_schema_closure(self.live, self.stage)
        self.assertEqual(result["source_chain"][-1], "0047_mpw_guest_email_recovery")

    def test_unknown_legacy_suffix_is_denied(self):
        path = self.live / "core/models.py"
        path.write_text(path.read_text() + "\n# unreviewed edit\n", encoding="utf-8")
        self.assertFalse(has_reviewed_legacy_suffix(self.live, SOURCE, "core/models.py"))
        with self.assertRaisesRegex(RuntimeError, "partial Moj Prop model"):
            check_schema_closure(self.live, self.stage)

    def test_unknown_legacy_admin_suffix_is_denied(self):
        path = self.live / "core/admin.py"
        path.write_text(path.read_text() + "\n# unreviewed edit\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "partial Moj Prop admin"):
            check_schema_closure(self.live, self.stage)

    def test_non_reviewed_partial_model_set_is_denied(self):
        path = self.live / "core/models.py"
        path.write_text(path.read_text() + "\nclass MojPropOffer(T):\n    pass\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "partial Moj Prop model"):
            check_schema_closure(self.live, self.stage)

    def test_duplicate_class_in_prefix_is_denied(self):
        path = self.live / "core/models.py"
        path.write_text("class MojPropRequest:\n    pass\n" + path.read_text(), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "duplicate Moj Prop class"):
            check_schema_closure(self.live, self.stage)


if __name__ == "__main__":
    unittest.main()
