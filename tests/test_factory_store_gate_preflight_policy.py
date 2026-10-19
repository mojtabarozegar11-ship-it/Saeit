"""Regression: live native factory listing must fail closed before a shared site write.

The private cPanel runtime has an additional Django FactoryReleaseGate contract;
the repository's older unit-only Django model does not prove live readiness.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FLOW = ROOT / ".github/workflows/vps-native-store-publish-free.yml"


class NativeStoreGatePreflightPolicy(unittest.TestCase):
    def test_release_gate_precedes_any_public_template_mutation(self):
        source = FLOW.read_text(encoding="utf-8")
        gate = "      - name: Read-only verify factory Release Gate before any public template write"
        mutation = "      - name: Stage release importer and narrowly update Django store card markup"
        activation = "      - name: Run Django dry-run and activate the one owner-approved free listing"
        self.assertIn(gate, source)
        self.assertLess(source.index(gate), source.index(mutation))
        self.assertLess(source.index(mutation), source.index(activation))

    def test_gate_requires_real_current_manifest_and_correct_factory_product(self):
        text = FLOW.read_text(encoding="utf-8")
        required = (
            'Gate.objects.filter(product_id=product.pk)',
            'gate.manifest_id is None',
            'gate.run_id is None',
            'gate.artifact_id is None',
            'release_manifest_is_current(gate.manifest,product,gate.run,gate.artifact)',
            'FACTORY_RELEASE_GATE_MISSING_REQUIRE_REAL_MANIFEST_INDEPENDENT_QA',
            'FACTORY_RELEASE_GATE_MANIFEST_STALE_OR_UNVERIFIED',
            'metadata.get("factory_software_qa")!="passed"',
            'products=Product.objects.filter(pk=131,price=0,currency="USD")',
        )
        for guard in required:
            with self.subTest(guard=guard):
                self.assertIn(guard, text)
        self.assertNotIn('Gate.objects.create(', text)
        self.assertNotIn('FactoryReleaseGate.objects.create(', text)
        self.assertNotIn('factory_managed=False', text)

    def test_protected_django_site_deploy_remains_locked(self):
        text = (ROOT / ".github/workflows/mojplaywin-main-deploy.yml").read_text(encoding="utf-8")
        self.assertIn('if: ${{ false }}', text)


if __name__ == "__main__":
    unittest.main()
