"""Reject P0 deployment path drift and missing production-cycle synchronization."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class FactoryP0InstallTargetTest(unittest.TestCase):
    def test_deployment_targets_the_real_manufacturer_runtime(self):
        canonical=(ROOT/"deploy/install_autonomous_factory_products.sh").read_text(encoding="utf8")
        workflow=(ROOT/".github/workflows/factory-p0-recovery-regressions.yml").read_text(encoding="utf8")
        self.assertIn('stage="$ops/autonomous-product-runtime"',canonical)
        self.assertIn('scripts="$stage/scripts"',canonical)
        self.assertIn('runtime="$ops/autonomous-product-runtime"',workflow)
        self.assertIn('target="$runtime/scripts"',workflow)
        self.assertNotIn('target="$base/scripts"',workflow)
    def test_installer_uses_same_lock_as_production_scheduler(self):
        installer=(ROOT/"deploy/install_autonomous_factory_products.sh").read_text(encoding="utf8")
        workflow=(ROOT/".github/workflows/factory-p0-recovery-regressions.yml").read_text(encoding="utf8")
        self.assertIn('exec 8>"$ops/autonomous-product-cycle.lock"',installer)
        self.assertIn('exec 8>"$ops/autonomous-product-cycle.lock"',workflow)
        self.assertIn('flock -w 180 8',workflow)
        self.assertIn('FACTORY_P0_CANONICAL_RUNTIME_MISSING_OR_UNSAFE',workflow)
        self.assertIn('FACTORY_P0_CANONICAL_RUNTIME_VERIFIED',workflow)
    def test_no_auto_publication_or_payment_release(self):
        workflow=(ROOT/".github/workflows/factory-p0-recovery-regressions.yml").read_text(encoding="utf8")
        self.assertIn('FACTORY_PUBLIC_PRODUCTS_PUBLISHED=0',workflow)
        self.assertIn('FACTORY_PAYMENT_CHANGED=false',workflow)
        self.assertIn('FACTORY_P0_PRIVATE_MODULE_ROLLBACK=RESTORED',workflow)
        self.assertIn('needs: technical-integrity',workflow)
        self.assertIn("github.ref == 'refs/heads/main'",workflow)

if __name__ == "__main__":
    unittest.main()
