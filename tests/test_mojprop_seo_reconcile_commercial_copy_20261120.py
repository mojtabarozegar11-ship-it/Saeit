"""Pure regression tests for reviewed sales-copy delta, no host operation."""
import unittest
from unittest.mock import patch
from scripts import mojprop_seo_reconcile_commercial_copy_20261120 as mod

class CopyReconciliationTests(unittest.TestCase):
    def test_each_reviewed_anchor_is_changed_once_and_functional_markup_preserved(self):
        protected = '<form id="keep"><input name="email"></form><script>let x=1;</script><style>p{color:red}</style>'
        for path, edits in mod.PATCHES.items():
            with self.subTest(path=path):
                head = '<html><head><title>Keep title</title></head><body>'
                source = (head + ''.join(old for old,new in edits)+protected+'</body></html>').encode()
                with patch.object(mod, "build_candidate", return_value=(source, {})):
                    result, receipt = mod.reconcile_candidate(path, b"fixture")
                text = result.decode()
                expected = source.decode()
                for old, new in edits:
                    expected = expected.replace(old,new,1)
                self.assertEqual(text, expected)
                self.assertIn(protected, text)
                self.assertEqual(receipt["copy_patch_count"],len(edits))
                self.assertFalse(receipt["deployment_authorized"])

    def test_missing_or_duplicate_anchor_fails_closed(self):
        edits = mod.PATCHES["index.html"]
        for invalid in ("", edits[0][0]*2):
            with self.subTest(invalid=bool(invalid)), patch.object(mod, "build_candidate",
                return_value=(('<head></head><body>'+invalid+'</body>').encode(), {})):
                with self.assertRaises(ValueError):
                    mod.reconcile_candidate("index.html", b"fixture")

    def test_original_builder_rejects_drift_and_unknown_routes(self):
        for path in ("index.html", "signals/index.html", "starter-30-trx/index.html", "../index.html"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                mod.reconcile_candidate(path,b"changed")

    def test_rules_and_contact_bodies_do_not_change(self):
        for path in ("rules/index.html","contact/index.html"):
            with self.subTest(path=path), patch.object(mod,"build_candidate",return_value=(b"<head></head><body>original</body>",{})):
                result, receipt = mod.reconcile_candidate(path,b"fixture")
                self.assertEqual(result,b"<head></head><body>original</body>")
                self.assertEqual(receipt["copy_patch_count"],0)
