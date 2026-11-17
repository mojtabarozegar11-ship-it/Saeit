"""Offline evidence that migration identity covers executable code, not operations alone.

Only temporary, non-imported Python text is inspected. No database, network,
production environment, customer data or mutation is accessed.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.mojprop_schema_preflight_c83 import (
    _class_signatures, migration_operations_signature,
)

BASE = """from django.db import migrations
from django.conf import settings

def forwards(apps, schema_editor):
    return "reviewed"

class Migration(migrations.Migration):
    dependencies = [("core", "0040_commercefunnelevent"),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.RunPython(forwards)]
"""


class WholeMigrationIntegrityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "0041_mojprop_request.py"
        self.path.write_text(BASE, encoding="utf-8")

    def fingerprint(self, source=None):
        if source is not None:
            self.path.write_text(source, encoding="utf-8")
        return migration_operations_signature(self.path)

    def test_approved_core_parent_rewrite_is_ignored(self):
        expected = self.fingerprint()
        changed = BASE.replace("0040_commercefunnelevent", "0039_previous_schema")
        self.assertEqual(expected, self.fingerprint(changed))

    def test_runpython_helper_change_is_rejected(self):
        expected = self.fingerprint()
        altered = BASE.replace('return "reviewed"', 'return "unreviewed"')
        self.assertNotEqual(expected, self.fingerprint(altered))

    def test_unreviewed_import_is_rejected(self):
        expected = self.fingerprint()
        self.assertNotEqual(expected, self.fingerprint("import os\n" + BASE))

    def test_executable_top_level_statement_is_rejected(self):
        expected = self.fingerprint()
        self.assertNotEqual(expected, self.fingerprint(BASE + "\nprint('side effect')\n"))

    def test_unreviewed_noncore_dependency_is_rejected(self):
        expected = self.fingerprint()
        edited = BASE.replace(
            "migrations.swappable_dependency(settings.AUTH_USER_MODEL)",
            "('auth', '0012_alter_user_first_name_max_length')",
        )
        self.assertNotEqual(expected, self.fingerprint(edited))

    def test_missing_dependency_is_denied(self):
        edited = BASE.replace(
            'dependencies = [("core", "0040_commercefunnelevent"),\n'
            '                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]',
            "dependencies = []",
        )
        with self.assertRaisesRegex(RuntimeError, "ambiguous core parent"):
            self.fingerprint(edited)

    def test_duplicate_core_parents_are_denied(self):
        edited = BASE.replace(
            '("core", "0040_commercefunnelevent"),',
            '("core", "0040_commercefunnelevent"), ("core", "0039_duplicate"),',
        )
        with self.assertRaisesRegex(RuntimeError, "ambiguous core parent"):
            self.fingerprint(edited)

    def test_duplicate_operations_blocks_are_denied(self):
        edited = BASE.replace(
            "operations = [migrations.RunPython(forwards)]",
            "operations = [migrations.RunPython(forwards)]\n"
            "    operations = [migrations.RunPython(forwards)]",
        )
        with self.assertRaisesRegex(RuntimeError, "ambiguous operations"):
            self.fingerprint(edited)

    def test_comments_without_executable_effect_do_not_change_fingerprint(self):
        expected = self.fingerprint()
        self.assertEqual(expected, self.fingerprint(BASE + "\n# harmless review annotation\n"))

    def test_identical_baseline_is_stable(self):
        first = self.fingerprint()
        self.assertEqual(first, self.fingerprint(BASE))


if __name__ == "__main__":
    unittest.main()
