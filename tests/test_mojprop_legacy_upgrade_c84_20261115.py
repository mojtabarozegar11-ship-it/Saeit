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
    migration_operations_signature,
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

    def test_duplicate_commercial_class_in_legacy_prefix_is_never_ignored(self):
        for relative, name in (
            ("core/models.py", "MojPropRequest"),
            ("core/admin.py", "MojPropRequestAdmin"),
        ):
            with self.subTest(relative=relative):
                dst = self.root / relative
                original = dst.read_text(encoding="utf-8")
                dst.write_text("class " + name + ":\n    pass\n\n" + original,
                               encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "duplicate Moj Prop class"):
                    check_schema_closure(self.root, SOURCE)
                dst.write_text(original, encoding="utf-8")

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

    def test_urlconf_comments_cannot_masquerade_as_live_business_routes(self):
        import ast
        target = self.root / "config/urls.py"
        target.parent.mkdir(parents=True)
        target.write_text(
            'from django.urls import path\n'
            'urlpatterns = []\n'
            '# path("moj-prop-intake/", fake)\n'
            '# path("moj-prop-status/", fake)\n'
            '# path("moj-prop-quote/<str:token>/", fake)\n',
            encoding="utf-8"
        )
        with patch.object(installer, "ROOT", self.root):
            installer.patch_urlconf(target)
        tree = ast.parse(target.read_text("utf-8"))
        actual = installer._declared_url_routes(target.read_text("utf-8"))
        self.assertEqual(set(actual), {
            "moj-prop-intake/", "moj-prop-status/",
            "moj-prop-quote/<str:token>/",
        })
        self.assertTrue(any(isinstance(node, ast.AugAssign) for node in tree.body))

    def test_urlconf_rejects_existing_business_route_bound_to_unreviewed_view(self):
        target = self.root / "config/urls.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        original = (
            'from django.urls import path\n'
            'urlpatterns = [path("moj-prop-intake/", attacker_view)]\n'
        )
        target.write_text(original, encoding="utf-8")
        with patch.object(installer, "ROOT", self.root):
            with self.assertRaisesRegex(RuntimeError, "unreviewed view"):
                installer.patch_urlconf(target)
        self.assertEqual(target.read_text("utf-8"), original)

    def test_urlconf_rejects_duplicate_live_routes_instead_of_claiming_success(self):
        target = self.root / "config/urls.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        original = (
            'from django.urls import path\n'
            'urlpatterns = [path("moj-prop-intake/", mojprop_intake), '
            'path("moj-prop-intake/", other_view)]\n'
        )
        target.write_text(original, encoding="utf-8")
        with patch.object(installer, "ROOT", self.root):
            with self.assertRaisesRegex(RuntimeError, "duplicate Moj Prop"):
                installer.patch_urlconf(target)
        self.assertEqual(target.read_text("utf-8"), original)

    def test_urlconf_with_real_business_routes_remains_unchanged(self):
        target = self.root / "config/urls.py"
        target.parent.mkdir(parents=True)
        source = (
            'from django.urls import path\n'
            'urlpatterns = [\n'
            '    path("moj-prop-intake/", mojprop_intake),\n'
            '    path("moj-prop-status/", mojprop_receipt_status),\n'
            '    path("moj-prop-quote/<str:token>/", customer_quote),\n'
            ']\n'
        )
        target.write_text(source, encoding="utf-8")
        with patch.object(installer, "ROOT", self.root):
            installer.patch_urlconf(target)
        self.assertEqual(target.read_text(encoding="utf-8"), source)

    def test_installer_does_not_rewrite_0040_marker_hidden_in_comment(self):
        migrations = self.root / "core/migrations"
        (migrations / "0040_known.py").write_text("class Migration: pass\n")
        unsafe = self.root / "comment-marker-migration.py"
        unsafe.write_text(
            '# ("core", "0040_commercefunnelevent")\n'
            'class Migration:\n'
            '    dependencies = [("core", "0038_unreviewed")]\n'
            '    operations = []\n'
        )
        target = migrations / "0041_mojprop_request.py"
        with patch.object(installer, "ROOT", self.root):
            with self.assertRaisesRegex(RuntimeError, "baseline parent is unreviewed"):
                installer.install_migration(unsafe, target)
        self.assertFalse(target.exists())

    def test_installer_rejects_duplicate_parent_marker_in_comment(self):
        migrations = self.root / "core/migrations"
        (migrations / "0040_known.py").write_text("class Migration: pass\n")
        source = SOURCE / "core/migrations/0041_mojprop_request.py"
        unsafe = self.root / "duplicated-baseline-marker.py"
        unsafe.write_text(source.read_text("utf-8") +
                          '\n# ("core", "0040_commercefunnelevent")\n')
        with patch.object(installer, "ROOT", self.root):
            with self.assertRaisesRegex(RuntimeError, "cannot be replaced uniquely"):
                installer.install_migration(
                    unsafe, migrations / "0041_mojprop_request.py"
                )
        self.assertFalse((migrations / "0041_mojprop_request.py").exists())

    def test_install_migration_rejects_two_competing_core_0040_heads(self):
        migrations = self.root / "core/migrations"
        for name in ("0040_branch_a.py", "0040_branch_b.py"):
            (migrations / name).write_text("class Migration: pass\n")
        target = migrations / "0041_mojprop_request.py"
        source = SOURCE / "core/migrations/0041_mojprop_request.py"
        with patch.object(installer, "ROOT", self.root):
            with self.assertRaisesRegex(RuntimeError, "ambiguous core migration parent"):
                installer.install_migration(source, target)
        self.assertFalse(target.exists())

    def test_install_migration_rejects_unknown_empty_core_history(self):
        target = self.root / "core/migrations/0041_mojprop_request.py"
        source = SOURCE / "core/migrations/0041_mojprop_request.py"
        with patch.object(installer, "ROOT", self.root):
            with self.assertRaisesRegex(RuntimeError, "reviewed core migration parent is missing"):
                installer.install_migration(source, target)
        self.assertFalse(target.exists())

    def test_migrations_directory_symlink_to_other_tenant_is_refused(self):
        path = self.root / "core/migrations"
        path.rmdir()
        outsider = self.root / "other-tenant-migrations"
        outsider.mkdir()
        path.symlink_to(outsider, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "unsafe Moj Prop migrations directory"):
            check_schema_closure(self.root, SOURCE)
        self.assertEqual(list(outsider.iterdir()), [])

    def test_staged_migrations_directory_symlink_is_rejected(self):
        # Validate preflight in a separate staged tree without any real
        # tenant or database mutation.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "core").mkdir()
            source_migrations = root / "migrations-copy"
            source_migrations.mkdir()
            (root / "core/migrations").symlink_to(
                source_migrations, target_is_directory=True
            )
            with self.assertRaisesRegex(RuntimeError, "unsafe Moj Prop migrations directory"):
                check_schema_closure(self.root, root)

    def test_live_model_or_admin_symlink_must_not_escape_tenant(self):
        for relative in ("core/models.py", "core/admin.py"):
            with self.subTest(relative=relative):
                path = self.root / relative
                original = path.read_bytes()
                outside = self.root / ("outside-" + Path(relative).name)
                outside.write_bytes(original)
                path.unlink()
                path.symlink_to(outside)
                with self.assertRaisesRegex(
                    RuntimeError, "unsafe live commercial source path"
                ):
                    check_schema_closure(self.root, SOURCE)
                self.assertEqual(outside.read_bytes(), original)
                path.unlink()
                path.write_bytes(original)

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

    def test_existing_migration_extra_code_rejected_even_when_operations_match(self):
        name = "0041_mojprop_request"
        original = (SOURCE / "core/migrations" / (name + ".py")).read_text("utf-8")
        dst = self.root / "core/migrations" / (name + ".py")
        dst.write_text(original + "\n\ndef unreviewed_migration_side_effect():\n"
                       "    raise RuntimeError('side effect')\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "existing live migration differs"):
            check_schema_closure(self.root, SOURCE)

    def test_extra_cross_app_dependency_cannot_hide_behind_selected_parent(self):
        source = self.root / "mig-original.py"
        tampered = self.root / "mig-extra-dependency.py"
        source.write_text(
            'class Migration:\n'
            '    dependencies = [("core", "0040_previous")]\n'
            '    operations = [1]\n',
            encoding="utf-8",
        )
        tampered.write_text(
            'class Migration:\n'
            '    dependencies = [("core", "0040_other"), '
            '("third_party", "0002_unreviewed")]\n'
            '    operations = [1]\n',
            encoding="utf-8",
        )
        self.assertNotEqual(migration_operations_signature(source),
                            migration_operations_signature(tampered))

    def test_migration_signature_ignores_only_selected_dependency_parent(self):
        a = self.root / "a.py"
        b = self.root / "b.py"
        a.write_text('class Migration:\n'
                     '    dependencies = [("core", "0040_old")]\n'
                     '    operations = [1]\n', encoding="utf-8")
        b.write_text('class Migration:\n'
                     '    dependencies = [("core", "0040_new")]\n'
                     '    operations = [1]\n', encoding="utf-8")
        self.assertEqual(migration_operations_signature(a),
                         migration_operations_signature(b))
        b.write_text(b.read_text("utf-8") + "\n"
                     "def unreviewed_helper(): return 1\n", encoding="utf-8")
        self.assertNotEqual(migration_operations_signature(a),
                            migration_operations_signature(b))



if __name__ == "__main__":
    unittest.main()
