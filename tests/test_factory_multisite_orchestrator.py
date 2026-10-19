"""Safety checks for private site distribution catalog generation."""
import importlib.util
import hashlib
import hmac
import os
import zipfile
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
        keys = self.products / "product-lifecycle"
        keys.mkdir(parents=True)
        self.key = "c1" * 32
        secret = keys / "reviewer-keys.json"
        secret.write_text(json.dumps({
            "schema": "saeit.factory.reviewer-keys.v1",
            "reviewers": {"independent-reviewer": self.key}
        }))
        os.chmod(secret, 0o600)

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

    def test_verified_product_fans_out_to_all_sites_without_sales(self):
        self.write_sites([
            {"id": name, "url": "https://example.org/" + name,
             "topics": topics, "status": "active", "owner_verified": True,
             "adapter_verified": True}
            for name, topics in (("farm", ["agriculture"]), ("games", ["gaming"]))
        ])
        folder = self.products / "digital-products" / "farm_tool"
        folder.mkdir(parents=True)
        archive = folder / "farm_tool-internal-qa.zip"
        with zipfile.ZipFile(archive, "w") as out:
            out.writestr("farm_tool/help.txt", "Sample verified artifact")
        sha = hashlib.sha256(archive.read_bytes()).hexdigest()
        source = "a" * 64
        (folder / "manufacturing_manifest.json").write_text(json.dumps({
            "recipe": "farm_tool", "qa_status": "passed", "artifact_sha256": sha,
            "source_sha256": source}))
        review = {
            "schema": "saeit.factory.distribution-review.v1",
            "artifact_sha256": sha, "source_sha256": source,
            "status": "approved", "sale_required": False,
            "reviewer": "verified-reviewer", "reviewer_id": "independent-reviewer",
            "producer_id": "factory-producer", "topics": ["agriculture"],
            "checks": {name: {"passed": True, "evidence": "Test report for " + name}
                       for name in module.REVIEWS}
        }
        message = json.dumps(review, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False).encode("utf8")
        review["reviewer_signature"] = hmac.new(
            bytes.fromhex(self.key), message, hashlib.sha256).hexdigest()
        (self.approvals / "farm_tool.json").write_text(json.dumps(review))
        result = module.build(self.registry, self.products, self.approvals, self.output)
        self.assertEqual(result["products_approved"], 1)
        self.assertEqual(result["sites_active"], 2)
        self.assertEqual(result["publications_verified"], 0)
        farm = module.load(self.output / "sites/farm/catalog.json")
        games = module.load(self.output / "sites/games/catalog.json")
        self.assertEqual(len(farm["catalog"]), 1)
        self.assertEqual(len(games["catalog"]), 1)
        self.assertEqual(farm["featured_ids"], ["farm_tool"])
        self.assertEqual(games["featured_ids"], [])

    def test_unsigned_approvals_cannot_be_forged_into_distribution(self):
        self.write_sites([{
            "id": "secure-site", "url": "https://example.org/",
            "topics": ["research"], "status": "active",
            "owner_verified": True, "adapter_verified": True,
        }])
        folder = self.products / "digital-products" / "research_product"
        folder.mkdir(parents=True)
        archive = folder / "research_product-internal-qa.zip"
        with zipfile.ZipFile(archive, "w") as out:
            out.writestr("research_product/readme.txt", "Real internal test")
        sha = hashlib.sha256(archive.read_bytes()).hexdigest()
        (folder / "manufacturing_manifest.json").write_text(json.dumps({
            "recipe": "research_product", "qa_status": "passed",
            "artifact_sha256": sha, "source_sha256": "a" * 64}))
        (self.approvals / "research_product.json").write_text(json.dumps({
            "schema": "saeit.factory.distribution-review.v1",
            "artifact_sha256": sha, "source_sha256": "a" * 64,
            "status": "approved", "sale_required": False,
            "reviewer": "claimed-reviewer", "reviewer_id": "independent-reviewer",
            "producer_id": "factory-producer", "topics": ["research"],
            "checks": {name: {"passed": True, "evidence": "Unverified claim text"}
                       for name in module.REVIEWS}
        }))
        report = module.build(self.registry, self.products, self.approvals, self.output)
        self.assertEqual(report["products_approved"], 0)
        self.assertEqual(len(report["products_blocked"]), 1)
        self.assertEqual(report["publications_verified"], 0)

    def test_seeds_never_claim_live_publication(self):
        source = module.load(ROOT / "config/factory_sites_seed.json")
        self.assertTrue(source["sites"])
        self.assertTrue(all(site["status"] == "pending" for site in source["sites"]))
        self.assertTrue(all(not site["owner_verified"] for site in source["sites"]))


if __name__ == "__main__":
    unittest.main()
