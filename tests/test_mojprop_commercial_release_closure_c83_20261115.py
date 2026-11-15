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
import shlex


def staged_tar_paths():
    workflow = Path(__file__).resolve().parents[1] / (
        ".github/workflows/mojprop-backend-controlled-release-20261115.yml"
    )
    text = workflow.read_text(encoding="utf-8")
    step = text.split("- name: Package only Moj Prop installer and page", 1)[1]
    line = next(line.strip() for line in step.splitlines()
                if line.strip().startswith("run: tar -cf "))
    args = shlex.split(line.removeprefix("run: "))
    if args[:2] != ["tar", "-cf"]:
        raise AssertionError("Unexpected release archive invocation")
    return set(args[3:])


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

    def test_existing_complete_live_model_and_admin_match_is_accepted(self):
        for name in ("models.py", "admin.py"):
            shutil.copyfile(SOURCE / "core" / name, self.live / "core" / name)
        self.assertFalse(check_schema_closure(self.live, SOURCE)["manual_deploy_authorized"])

    def test_existing_live_offer_model_drift_requires_independent_reconciliation(self):
        for name in ("models.py", "admin.py"):
            shutil.copyfile(SOURCE / "core" / name, self.live / "core" / name)
        model = self.live / "core/models.py"
        original = model.read_text(encoding="utf-8")
        self.assertIn("class MojPropOffer(T):", original)
        model.write_text(
            original.replace("class MojPropOffer(T):",
                             "class MojPropOffer(T):\n    forged_column = True", 1),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(RuntimeError, "differs from reviewed source"):
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

    def test_unknown_live_schema_revision_is_denied_before_migration(self):
        path = self.live / "core/migrations/0046_unreviewed_feature.py"
        path.write_text("class Migration: pass\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "unreviewed later"):
            check_schema_closure(self.live, SOURCE)
        path.rename(self.live / "core/migrations/0041_conflicting_branch.py")
        with self.assertRaisesRegex(RuntimeError, "conflicting core migration"):
            check_schema_closure(self.live, SOURCE)

    def test_production_migration_targets_only_mojprop_core_0046(self):
        body = (SOURCE / "scripts/deploy_mojplaywin_moj_prop_backend.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"core", "0046_signal_free_subscription", "--noinput"', body)
        self.assertNotIn('["manage.py", "migrate", "--noinput"]', body)
        self.assertLess(
            body.index("check_schema_closure(ROOT, staged_root)"),
            body.index('"0046_signal_free_subscription", "--noinput"'),
        )

    def test_missing_staged_migration_causes_preflight_failure(self):
        stage = Path(self.sandbox.name) / "stage"
        for relative in (
            Path("core/models.py"), Path("core/admin.py"), Path("config/urls.py"), Path("config/settings.py"),
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

    def test_existing_applied_intake_migration_is_not_reparented(self):
        live_migrations = self.live / "core/migrations"
        target = live_migrations / "0041_mojprop_request.py"
        original = (SOURCE / "core/migrations/0041_mojprop_request.py").read_text(
            encoding="utf-8"
        ).replace(
            '("core", "0040_commercefunnelevent")',
            '("core", "0039_educationassessment_educationattempt_and_more")',
        )
        target.write_text(original, encoding="utf-8")
        (live_migrations / "0040_commercefunnelevent.py").write_text(
            "class Migration: pass\n", encoding="utf-8"
        )
        with patch.object(installer, "ROOT", self.live):
            with contextlib.redirect_stdout(io.StringIO()):
                installer.install_migration(
                    SOURCE / "core/migrations/0041_mojprop_request.py", target
                )
        self.assertEqual(target.read_text(encoding="utf-8"), original)

    def test_existing_intake_migration_with_different_operations_refused(self):
        target = self.live / "core/migrations/0041_mojprop_request.py"
        target.write_text(
            (SOURCE / "core/migrations/0041_mojprop_request.py")
            .read_text(encoding="utf-8")
            .replace("migrations.CreateModel(", "migrations.RunPython("),
            encoding="utf-8",
        )
        before = target.read_bytes()
        with patch.object(installer, "ROOT", self.live):
            with self.assertRaisesRegex(RuntimeError, "different previously applied"):
                installer.install_migration(
                    SOURCE / "core/migrations/0041_mojprop_request.py", target
                )
        self.assertEqual(target.read_bytes(), before)

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

    def test_separate_free_registration_modules_and_schema_are_all_in_release_tar(self):
        archive = staged_tar_paths()
        for path in (
            "core/signal_free_models.py", "core/signal_free_views.py",
            "core/migrations/0046_signal_free_subscription.py",
            "config/settings.py",
        ):
            with self.subTest(path=path):
                self.assertIn(path, archive)
                self.assertIn(Path(path), installer.ALL_FILES)
        workflow = (SOURCE / ".github/workflows/mojprop-backend-controlled-release-20261115.yml").read_text("utf-8")
        self.assertLess(
            workflow.index("- name: Deploy Moj Prop intake backend with backup and migration"),
            workflow.index("- name: Update only /moj-prop/ commercial catalog"),
        )
        self.assertIn("SIGNAL_FREE_OPTIN_BACKEND_GET=PASS", workflow)
        self.assertIn("SIGNAL_FREE_PUBLIC_PAGE=PASS", workflow)

    def test_live_owner_models_admin_settings_receive_only_scoped_free_additions(self):
        from contextlib import redirect_stdout
        model = self.live / "core/models.py"
        admin = self.live / "core/admin.py"
        settings = self.live / "config/settings.py"
        settings.parent.mkdir(parents=True, exist_ok=True)
        model.write_text("from django.db import models\\nclass T: pass\\nclass Unrelated: pass\\n", encoding="utf-8")
        admin.write_text(
            "from django.contrib import admin\\nfrom django.contrib.admin import ModelAdmin\\n"
            "class OwnerAdmin: pass\\n",
            encoding="utf-8",
        )
        settings.write_text("EMAIL_BACKEND='smtp'\\nenv.bool('X', default=False)\\n", encoding="utf-8")
        with patch.object(installer, "ROOT", self.live), redirect_stdout(io.StringIO()):
            for _ in range(2):
                installer.patch_free_model_import(model, SOURCE / "core/models.py")
                installer.patch_free_admin_readonly(admin, SOURCE / "core/admin.py")
                installer.patch_free_settings(settings, SOURCE / "config/settings.py")
        self.assertEqual(model.read_text().count("from .signal_free_models import MojSignalFreeSubscription"), 1)
        self.assertEqual(admin.read_text().count("class MojSignalFreeSubscriptionAdmin("), 1)
        self.assertIn("OwnerAdmin", admin.read_text())
        self.assertIn("class Unrelated", model.read_text())
        self.assertIn("default=False", settings.read_text())
        self.assertEqual(settings.read_text().count("MOJTABA_SIGNAL_FREE_SIGNUP_ENABLED"), 2)

    def test_only_three_root_free_routes_are_added_once(self):
        target = self.live / "config/urls.py"
        target.parent.mkdir(exist_ok=True)
        target.write_text("from django.urls import path\\nurlpatterns = []\\n", encoding="utf-8")
        with patch.object(installer, "ROOT", self.live):
            with contextlib.redirect_stdout(io.StringIO()):
                installer.patch_free_urlconf(target)
                once = target.read_text()
                installer.patch_free_urlconf(target)
        self.assertEqual(target.read_text(), once)
        for uri in ("moj-signal-free-subscribe/", "moj-signal-free-confirm/<str:token>/",
                    "moj-signal-free-unsubscribe/<str:token>/"):
            self.assertEqual(once.count('path("' + uri + '"'), 1)
        self.assertNotIn("email.send(", once)
        self.assertNotIn("trx", once.lower())

    def test_unknown_existing_signal_module_is_preserved_by_schema_preflight(self):
        path = self.live / "core/signal_free_models.py"
        path.write_text("class UnknownLiveCustom: pass\\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "unreviewed live signal-free module drift"):
            check_schema_closure(self.live, SOURCE)
        self.assertIn("UnknownLiveCustom", path.read_text())

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
