"""Ensure Moj Prop's initial migration actually matches its Django models."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class MojPropMigrationConsistencyTests(TestCase):
    def test_migration_has_no_uncommitted_schema_changes(self):
        output = StringIO()
        # --check fails when Django would generate another migration.
        call_command("makemigrations", "prop_firm", check=True, dry_run=True,
                     verbosity=1, stdout=output)
        self.assertIn("No changes detected", output.getvalue())
