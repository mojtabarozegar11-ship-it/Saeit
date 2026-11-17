"""Prove conflicting Moj Prop class declarations fail before source upgrade.

Only temporary synthetic Python source parsed as AST; no network or DB.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.mojprop_schema_preflight_c83 import _class_signatures, _classes


class DuplicateMojPropClassTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.file = Path(tmp.name) / "models.py"

    def signatures(self, source):
        self.file.write_text(source, encoding="utf-8")
        return _class_signatures(self.file)

    def test_duplicate_live_request_class_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "duplicate Moj Prop class"):
            self.signatures(
                "class MojPropRequest:\n    passed = False\n"
                "class MojPropRequest:\n    passed = True\n"
            )

    def test_duplicate_admin_class_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "duplicate Moj Prop class"):
            self.signatures(
                "class MojPropRequestAdmin:\n    pass\n"
                "class MojPropRequestAdmin:\n    pass\n"
            )

    def test_unrelated_legacy_class_collisions_do_not_break_upgrade(self):
        # This guard is specifically for the commercial class namespace and
        # must not unexpectedly reject owner-preserved unrelated declarations.
        found = self.signatures("class T:\n    pass\nclass T:\n    value = 1\n")
        self.assertEqual(set(found), {"T"})

    def test_all_three_distinct_reviewed_models_are_recognized(self):
        found = self.signatures(
            "class MojPropRequest:\n    pass\n"
            "class MojPropOffer:\n    pass\n"
            "class MojPropDeliveryEvidence:\n    pass\n"
        )
        self.assertEqual(set(found), {
            "MojPropRequest", "MojPropOffer", "MojPropDeliveryEvidence",
        })
        self.assertEqual(_classes(self.file), set(found))

    def test_duplicate_of_later_offer_model_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "duplicate Moj Prop class"):
            self.signatures(
                "class MojPropOffer:\n    pass\n"
                "class MojPropOffer:\n    modified = 1\n"
            )


if __name__ == "__main__":
    unittest.main()
