"""Contract tests for non-human-proving funnel event semantics."""

from pathlib import Path
import ast
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "command_center" / "commerce_funnel.py"


class FunnelEventSemanticsTests(unittest.TestCase):
    def test_semantics_contract_is_explicit_and_read_only(self):
        source = SOURCE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = {
            node.targets[0].id
            for node in tree.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        }
        self.assertIn("EVENT_SEMANTICS", names)
        self.assertIn('"event_semantics": EVENT_SEMANTICS', source)
        self.assertIn('"read_only": True', source)

    def test_request_level_checkout_is_not_human_or_sale_evidence(self):
        source = SOURCE.read_text(encoding="utf-8")
        start = source.index('    "begin_checkout": {')
        end = source.index('    },', start) + len('    },')
        block = source[start:end]
        self.assertIn('"classification": "request_level"', block)
        self.assertIn('"human_evidence": False', block)
        self.assertIn('"sale_evidence": False', block)
        self.assertIn("bots, monitoring and internal verification", block)

    def test_invoice_and_payment_events_remain_distinct(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertLess(source.index('    "invoice_created": {'),
                        source.index('    "payment_confirmed": {'))
        invoice = source[source.index('    "invoice_created": {'):
                       source.index('    "payment_confirmed": {')]
        self.assertIn('"sale_evidence": False', invoice)


if __name__ == "__main__":
    unittest.main()
