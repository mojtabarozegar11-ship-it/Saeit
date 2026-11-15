"""No-host regression coverage for Moj Prop commercial deployment closure.

A green test is SOURCE ONLY: real database restore / Passenger and approved
buyer charging remain separate release gates.
"""
import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import deploy_mojplaywin_moj_prop_backend as installer
from scripts.mojprop_schema_preflight_c83 import (
    MIGRATIONS, MODELS, MODULES, check_schema_closure,
)
from tests.test_mojprop_backend_release_archive_c82_20261115 import staged_tar_paths


SOURCE = Path(__file__).resolve().parents[1]


class CommercialBackendClosureTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory()
        self.addCleanup(self.sandbox.cleanup)
        self.live = Path(self.sandbox.name) / "live"
        (self.live / "core/migrations").mkdir(parents=True)
        (self.live / "core/models.py").write_text(
            "class Unrelated: pass\n", encoding="utf-8"
        )
        (self.live / "core/admin.py").write_text(
            "class UnrelatedAdmin: pass\n", encoding="utf-8"
        )

    def test_full_staged_schema_closure_for_real_repo(self):
        result = check_schema_closure(self.live, SOURCE)
        self.assertEqual(result["source_chain"], list(MIGRATIONS))
        self.assertEqual(result["models"], len(MODELS))
        self.assertFalse(result["live_db_restored"])
        self.assertFalse(result["manual_deploy_authorized"])

    def test_tar_contains_all_installer_dependencies(self):
        content = staged_tar_paths()
        for relative in installer.ALL_FILES:
            with self.subTest(path=str(relative)):
                self.assertIn(str(relative), content)
        self.assertIn("scripts/mojprop_schema_preflight_c83.py", content)

    def test_all_commercial_schema_migrations_are_backed_up_and_replaced(self):
        for name in MIGRATIONS:
            relative = Path(f"core/migrations/{name}.py")
            with self.subTest(migration=name):
                self.assertIn(relative, installer.ALL_FILES)
                self.assertIn(relative, installer.REPLACE_FILES)
        for filename in MODULES:
            self.assertIn(Path(filename), installer.REPLACE_FILES)

    def test_partially_installed_request_model_refused_before_mutation(self):
        (self.live / "core/models.py").write_text(
            "class MojPropRequest: pass\n", encoding="utf-8"
        )
        before = (self.live / "core/models.py").read_bytes()
        with self.assertRaisesRegex(RuntimeError, "partial Moj Prop model"):
            check_schema_closure(self.live, SOURCE)
        self.assertEqual((self.live / "core/models.py").read_bytes(), before)

    def test_partially_installed_admin_refused_before_mutation(self):
        (self.live / "core/admin.py").write_text(
            "class MojPropRequestAdmin: pass\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(RuntimeError, "partial Moj Prop admin"):
            check_schema_closure(self.live, SOURCE)

    def test_unknown_migration_operations_not_overwritten(self):
        target = self.live / "core/migrations/0042_mojprop_offer.py"
        original = (SOURCE / "core/migrations/0042_mojprop_offer.py").read_text()
        target.write_text(original.replace("migrations.CreateModel(", "migrations.RunPython("),
                          encoding="utf-8")
        before = target.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "existing live migration differs"):
            check_schema_closure(self.live, SOURCE)
        self.assertEqual(target.read_bytes(), before)

    def test_missing_staged_migration_causes_preflight_failure(self):
        stage = Path(self.sandbox.name) / "stage"
        for relative in (
            Path("core/models.py"), Path("core/admin.py"), Path("config/urls.py"),
            *(Path(name) for name in MODULES),
            *(Path(f"core/migrations/{name}.py") for name in MIGRATIONS),
        ):
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SOURCE / relative, target)
        missing = stage / "core/migrations/0045_mojprop_delivery_evidence.py"
        missing.unlink()
        with self.assertRaisesRegex(RuntimeError, "missing or unsafe staged"):
            check_schema_closure(self.live, stage)

    def test_migration_0041_parent_never_depends_on_0045(self):
        live_migrations = self.live / "core/migrations"
        for name in ("0040_commercefunnelevent", "0045_mojprop_delivery_evidence"):
            (live_migrations / (name + ".py")).write_text(
                "class Migration: pass\n", encoding="utf-8"
            )
        target = live_migrations / "0041_mojprop_request.py"
        with patch.object(installer, "ROOT", self.live):
            with contextlib.redirect_stdout(io.StringIO()):
                installer.install_migration(
                    SOURCE / "core/migrations/0041_mojprop_request.py", target
                )
        installed = target.read_text(encoding="utf-8")
        self.assertIn('("core", "0040_commercefunnelevent")', installed)
        self.assertNotIn('("core", "0045_mojprop_delivery_evidence")', installed)

    def test_fresh_admin_installer_uses_current_main_import(self):
        target = self.live / "core/admin.py"
        target.write_text(
            "from django.contrib import admin\n"
            "from django.contrib.admin import ModelAdmin\n", encoding="utf-8"
        )
        with patch.object(installer, "ROOT", self.live):
            with contextlib.redirect_stdout(io.StringIO()):
                installer.patch_admin(target, SOURCE / "core/admin.py")
        updated = target.read_text(encoding="utf-8")
        for admin in ("MojPropRequestAdmin", "MojPropOfferAdmin",
                      "MojPropDeliveryEvidenceAdmin"):
            self.assertIn("class " + admin + "(", updated)

    def test_quote_route_installed_once_and_never_pays(self):
        target = self.live / "config/urls.py"
        target.parent.mkdir(exist_ok=True)
        target.write_text(
            "from django.urls import path\nurlpatterns = []\n",
            encoding="utf-8",
        )
        with patch.object(installer, "ROOT", self.live):
            with contextlib.redirect_stdout(io.StringIO()):
                installer.patch_urlconf(target)
                once = target.read_text(encoding="utf-8")
                installer.patch_urlconf(target)
        self.assertEqual(target.read_text(encoding="utf-8"), once)
        self.assertEqual(once.count('path("moj-prop-intake/"'), 1)
        self.assertEqual(once.count('path("moj-prop-status/"'), 1)
        self.assertEqual(once.count('path("moj-prop-quote/<str:token>/"'), 1)
        self.assertIn("from core.mojprop_quote_views import customer_quote", once)
        self.assertNotIn("trx", once.lower())


if __name__ == "__main__":
    unittest.main()
