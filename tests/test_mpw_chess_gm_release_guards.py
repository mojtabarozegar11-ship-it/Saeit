"""Static release guards for the staged final Grandmaster chess PDF.

No production DB, private assets, network, or payment rails are accessed.
"""
import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "core/chess_ebook_delivery.py"
PREFLIGHT = ROOT / "catalog/mojplaywin/chess-grandmaster-2026-release-preflight.json"
CONFIG = ROOT / "catalog/mojplaywin/chess-grandmaster-2026-safe-delivery-config.json"
EXPECTED_SHA = "3837fc3cb21ed1a2e7c33e0db8f8e10d158583309b02b97d4d674d25a147207a"
FINAL_FILENAME = "MojPlayWin_Chess_Grandmaster_Final_Covered_2026.pdf"
EXPECTED_SIZE = 3631972
OLD_SHA = "d284d559bfac931cffe11e97561ac442d63dae5d8eda4bc04e84dd2c26022a1b"


def constants_from_source():
    tree = ast.parse(DELIVERY.read_text(encoding="utf-8"))
    values = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        name = node.targets[0].id
        if name == "PDF_PATH":
            assert isinstance(node.value, ast.Call) and node.value.func.id == "Path"
            values[name] = ast.literal_eval(node.value.args[0])
        elif name in ("EXPECTED_SHA256", "EXPECTED_BYTES", "DOWNLOAD_NAME", "BOOK_PRODUCT_ID"):
            values[name] = ast.literal_eval(node.value)
    return values


class GrandmasterReleaseGuards(unittest.TestCase):
    def test_manifest_matches_staged_download(self):
        manifest = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
        values = constants_from_source()
        asset = manifest["private_asset"]
        self.assertEqual(manifest["product_id"], 72)
        self.assertEqual(manifest["pages"], 415)
        self.assertEqual(values["PDF_PATH"], asset["target"])
        self.assertEqual(values["DOWNLOAD_NAME"], asset["filename"])
        self.assertEqual(values["EXPECTED_BYTES"], EXPECTED_SIZE)
        self.assertEqual(asset["bytes"], EXPECTED_SIZE)
        self.assertEqual(values["EXPECTED_SHA256"], EXPECTED_SHA)
        self.assertEqual(asset["sha256"], EXPECTED_SHA)
        self.assertEqual(values["BOOK_PRODUCT_ID"], "mojplaywin-chess-improvement-2026")

    def test_private_asset_is_outside_public_website(self):
        from pathlib import PurePosixPath
        values = constants_from_source()
        path = PurePosixPath(values["PDF_PATH"])
        self.assertTrue(path.is_absolute())
        self.assertEqual(path.name, FINAL_FILENAME)
        self.assertEqual(path.parts[:4], ("/", "home", "zomorod2", "MojPlayWin_Private_Assets"))
        self.assertNotIn("public_html", path.parts)
        self.assertNotIn("static", path.parts)

    def test_old_book_cannot_be_delivered_by_staged_view(self):
        text = DELIVERY.read_text(encoding="utf-8")
        self.assertNotIn(OLD_SHA, text)
        self.assertNotIn("MojPlayWin_Science_and_Practice_of_Chess_Improvement.pdf", text)

    def test_staged_endpoint_checks_verified_payment_and_file_hash(self):
        text = DELIVERY.read_text(encoding="utf-8")
        for clause in (
            'metadata.get("asset_verified") is not True',
            'metadata.get("payment_live") is not True',
            'if not product.active:',
            'status="paid"',
            'status="succeeded"',
            'event_type="payment.succeeded"',
            'entry_type="payment"',
            'hashlib.sha256',
            'as_attachment=True',
            '"Cache-Control"',
        ):
            self.assertIn(clause, text, clause)

    def test_commerce_delivery_relative_path_is_exact_and_private(self):
        manifest = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
        proposed = json.loads(CONFIG.read_text(encoding="utf-8"))
        private_path = Path(proposed["proposed_product_metadata"]["mpw_commerce"]["private_file"])
        self.assertFalse(private_path.is_absolute())
        self.assertNotIn("..", private_path.parts)
        self.assertNotIn("public_html", private_path.parts)
        self.assertEqual(
            private_path.as_posix(),
            "store/chess-improvement/MojPlayWin_Chess_Grandmaster_Final_Covered_2026.pdf",
        )
        self.assertEqual(private_path.name, manifest["private_asset"]["filename"])
        self.assertTrue(proposed["final_book"]["live_private_asset_root_verified"])

    def test_owner_rights_attestation_does_not_enable_sale(self):
        manifest = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        declared = manifest["rights_declaration"]
        self.assertEqual(declared["declared_by"], "Mojtaba Roozegar")
        self.assertEqual(declared["attestation_status"], "OWNER_DECLARED_NOT_INDEPENDENTLY_VERIFIED")
        self.assertIn("text, images, and diagrams", declared["claim"])
        self.assertTrue(config["owner_declaration"]["attests_text_images_diagrams_and_commercial_distribution"])
        self.assertFalse(config["owner_declaration"]["third_party_provenance_review_complete"])
        self.assertIs(config["proposed_product_metadata"]["rights_owner_attested"], True)
        self.assertIs(config["proposed_product_metadata"]["mpw_commerce"]["enabled"], False)
        self.assertIs(manifest["public_active"], False)
        self.assertIs(manifest["checkout_enabled"], False)

    def test_configuration_remains_explicitly_unreleased(self):
        manifest = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
        proposed = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertIs(manifest["public_active"], False)
        self.assertIs(manifest["checkout_enabled"], False)
        self.assertIs(proposed["proposed_product_metadata"]["mpw_commerce"]["enabled"], False)
        self.assertEqual(proposed["release_state"], "STAGING_MANIFEST_ONLY_DO_NOT_TREAT_AS_DEPLOYED")
        self.assertEqual(proposed["final_book"]["sha256"], EXPECTED_SHA)
        self.assertEqual(proposed["final_book"]["bytes"], EXPECTED_SIZE)


if __name__ == "__main__":
    unittest.main()
