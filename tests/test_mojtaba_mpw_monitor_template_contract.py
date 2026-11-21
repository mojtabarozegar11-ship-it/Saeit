"""Canonical telemetry must actually be visible, never silently ignored in HTML."""
from pathlib import Path
import unittest

TEMPLATE = (Path(__file__).resolve().parents[1] / "command_center" /
            "templates" / "command_center" / "mpw_agent_monitor.html")


class CanonicalMonitorTemplateTests(unittest.TestCase):
    def test_site_only_staff_dashboard_shows_separate_canonical_receipt_section(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn('id="canonical"', text)
        self.assertIn('data.canonical_public_monitor', text)
        self.assertIn('successful_public_observation_receipts_24h', text)
        self.assertIn('legacy_collector_retirement_authorized', text)
        self.assertIn('panel.replaceChildren()', text)
        self.assertIn('el.textContent=', text)
        self.assertNotIn('panel.innerHTML=', text)
