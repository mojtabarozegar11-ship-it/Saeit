"""Safety checks for private site distribution catalog generation."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("catalogs", ROOT / "scripts/factory_multisite_orchestrator.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.registry = self.base / "sites.json"
        self.products = self.base / "private-products"
        self.approvals = self.base / "private-approvals"
        self.output = self.base / "private-site-catalogs"
        self.approvals.mkdir()
        (self.products / "digital-products").mkdir(parents=True)

    def write_sites(self, sites):
        self.registry.write_text(json.dumps({
            "schema": "saeit.factory.sites.v1", "sites": sites
        }), encoding="utf-8")

    def test_no_quality_approved_products_means_no_products_distributed(self):
        self.write_sites([{
            "id": "main-site", "url": "https://example.org/",
            "topics": ["research"], "status": "active",
            "owner_verified": True, "adapter_verified": True,
        }])
        result = module.build(self.registry, self.products, self.approvals, self.output)
        self.assertEqual(result["products_approved"], 0)
        self.assertEqual(result["publications_verified"], 0)
        self.assertEqual(result["sites_active"], 1)
        self.assertEqual(module.load(self.output / "sites/main-site/catalog.json")["catalog"], [])

    def test_unknown_future_site_must_be_verified_before_activation(self):
        self.write_sites([{
            "id": "future-site", "url": "https://example.org/new/",
            "topics": ["education"], "status": "pending",
            "owner_verified": False, "adapter_verified": False,
        }])
        result = module.build(self.registry, self.products, self.approvals, self.output)
        self.assertEqual(result["sites_active"], 0)
        self.assertEqual(result["sites_known"], 1)

    def test_unverified_active_site_rejected(self):
        self.write_sites([{
            "id": "not-owned", "url": "https://example.org/",
            "topics": ["research"], "status": "active",
            "owner_verified": False, "adapter_verified": False,
        }])
        with self.assertRaisesRegex(ValueError, "UNVERIFIED_ACTIVE_SITE"):
            module.build(self.registry, self.products, self.approvals, self.output)

    def test_seeds_never_claim_live_publication(self):
        source = module.load(ROOT / "config/factory_sites_seed.json")
        self.assertTrue(source["sites"])
        self.assertTrue(all(site["status"] == "pending" for site in source["sites"]))
        self.assertTrue(all(not site["owner_verified"] for site in source["sites"]))


if __name__ == "__main__":
    unittest.main()
