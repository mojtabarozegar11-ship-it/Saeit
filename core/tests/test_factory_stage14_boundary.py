from pathlib import Path
from django.test import SimpleTestCase

class Stage14BoundaryTests(SimpleTestCase):
    def test_brain_stops_after_packaging_pricing(self):
        source=(Path(__file__).resolve().parents[1]/"autonomous_brain.py").read_text()
        self.assertIn('"packaged_priced": "phase_14_complete"',source)
        self.assertIn("Stages 1-14 are complete",source)

    def test_release_lineage_requires_packaging_pricing(self):
        source=(Path(__file__).resolve().parents[1]/"factory_governance.py").read_text()
        marker="def _assert_release_evidence_current"
        release=source[source.index(marker):]
        self.assertIn('"product_package_price"',release)
        self.assertIn('"product_launch_candidate"',release)

    def test_launch_candidate_requires_packaged_priced(self):
        source=(Path(__file__).resolve().parents[1]/"factory_tool_pack.py").read_text()
        marker="def launch_candidate"
        launch=source[source.index(marker):]
        self.assertIn('factory_state") != "packaged_priced"',launch)
        self.assertIn('"package_pricing_digest"',launch)
