"""Guard exact no-data-mutation migration state for the Moj Prop lead funnel."""
import importlib
import unittest

from django.db import migrations


class CommerceFunnelLeadChoiceMigrationTests(unittest.TestCase):
    def test_single_choice_change_only_no_data_ddl_or_invoice_operation(self):
        old_module = importlib.import_module("core.migrations.0040_commercefunnelevent")
        new_module = importlib.import_module(
            "core.migrations.0048_alter_commercefunnelevent_event_name"
        )
        previous = old_module.Migration.operations[0]
        self.assertIsInstance(previous, migrations.CreateModel)
        original_field = dict(previous.fields)["event_name"]
        amendment = new_module.Migration.operations
        self.assertEqual(len(amendment), 1)
        self.assertIsInstance(amendment[0], migrations.AlterField)
        op = amendment[0]
        self.assertEqual((op.model_name, op.name),
                         ("commercefunnelevent", "event_name"))
        self.assertEqual(new_module.Migration.dependencies,
                         [("core", "0047_mpw_guest_email_recovery")])
        self.assertEqual(op.field.max_length, original_field.max_length)
        old_choices = list(original_field.choices)
        new_choices = list(op.field.choices)
        self.assertEqual(new_choices[:3], old_choices[:3])
        self.assertEqual(new_choices[3], ("lead_submit", "Manual lead submitted"))
        self.assertEqual(new_choices[4:], old_choices[3:])
        self.assertEqual(len(new_choices), len(old_choices) + 1)

    def test_migration_has_no_sql_data_execution_or_schema_shape_change(self):
        migration = importlib.import_module(
            "core.migrations.0048_alter_commercefunnelevent_event_name"
        )
        op, = migration.Migration.operations
        self.assertEqual(op.field.get_internal_type(), "CharField")
        self.assertIsNone(op.field.db_column)
        self.assertFalse(op.field.null)
        self.assertIsNone(op.field.default.__class__.__name__ == "NoneType" or None)
        self.assertEqual(op.field.max_length, 32)
        self.assertNotIn("RunPython", repr(migration.Migration.operations))
        self.assertNotIn("RunSQL", repr(migration.Migration.operations))


if __name__ == "__main__":
    unittest.main()
