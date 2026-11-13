"""Atelier future-registration commerce compatibility; no database writes."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/atelier_interior_register_native_draft_20261021.py"
spec = importlib.util.spec_from_file_location("atelier_registration", SCRIPT)
registration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(registration)


class DraftCompatibility(unittest.TestCase):
    def test_draft_file_pointer_is_relative_and_permissions_remain_closed(self):
        metadata = registration.intended_metadata()
        relative = metadata["mpw_commerce"]["private_file"]
        self.assertEqual(relative, registration.ARCHIVE.name)
        self.assertFalse(Path(relative).is_absolute())
        self.assertNotIn("..", Path(relative).parts)
        self.assertFalse(metadata["mpw_commerce"]["enabled"])
        self.assertFalse(metadata["factory_publication_permission"])
        self.assertFalse(metadata["license_verified"])
        self.assertFalse(metadata["quality_approved"])

    def test_new_registration_uses_commerce_eligible_digital_type(self):
        source = SCRIPT.read_text(encoding="utf8")
        self.assertIn('kwargs = dict(title=TITLE, product_type="digital"', source)
        self.assertNotIn('kwargs = dict(title=TITLE, product_type="website_template"', source)
        self.assertIn('active=False, owner_id=owner', source)


if __name__ == "__main__":
    unittest.main()
