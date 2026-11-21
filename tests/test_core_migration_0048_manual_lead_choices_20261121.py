"""Isolated source checks for the manual-lead choice migration."""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "core" / "migrations" / "0048_alter_commercefunnelevent_event_name.py"


class ManualLeadChoiceMigrationSourceTest(unittest.TestCase):
    def test_migration_is_metadata_only_and_exactly_one_operation(self):
        tree = ast.parse(MIGRATION.read_text(encoding="utf8"))
        operations = [
            call for call in ast.walk(tree)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr in ("AlterField", "CreateModel", "RunPython",
                                  "RunSQL", "AddField", "RemoveField")
        ]
        self.assertEqual(len(operations), 1)
        self.assertEqual(operations[0].func.attr, "AlterField")
        fields = {k.arg: k.value for k in operations[0].keywords}
        self.assertEqual(fields["model_name"].value, "commercefunnelevent")
        self.assertEqual(fields["name"].value, "event_name")

    def test_manual_lead_choice_and_no_payment_logic(self):
        src = MIGRATION.read_text(encoding="utf8")
        self.assertIn('("lead_submit", "Manual lead submitted")', src)
        self.assertIn('("core", "0047_mpw_guest_email_recovery")', src)
        self.assertNotIn("RunPython(", src)
        self.assertNotIn("RunSQL(", src)
        self.assertNotIn("default=", src)
        self.assertNotIn("recipient=", src)


if __name__ == "__main__":
    unittest.main()
