"""Real registry contract, security, revenue-accounting and CLI tests. No remote calls."""
from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ops/revenue/mojtaba_commercial_readiness_v1.py"
REGISTRY = ROOT / "ops/revenue/mojtaba_commercial_offers_v1.json"
SPEC = importlib.util.spec_from_file_location("commercial_readiness_v1", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


class PortfolioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = MOD.read_registry(REGISTRY)
        cls.report = MOD.assess(ROOT, cls.registry)

    def changed(self, **values):
        doc = copy.deepcopy(self.registry)
        doc["offers"][0].update(values)
        return doc

    def check_block(self, **changes):
        with self.assertRaises(MOD.ContractError):
            MOD.assess(ROOT, self.changed(**changes))

    def test_01_registry_schema_exact(self):
        self.assertEqual(self.registry["schema"], MOD.SCHEMA)

    def test_02_canonical_bot_exact_and_all_offers(self):
        self.assertEqual(self.registry["canonical_bot_id"], "mojtaba.bot.ai")
        self.assertTrue(all(x["canonical_bot_id"] == "mojtaba.bot.ai" for x in self.registry["offers"]))

    def test_03_15_distinct_product_and_service_scopes(self):
        self.assertEqual(len(self.registry["offers"]), 15)
        self.assertEqual(len({x["offer_id"] for x in self.registry["offers"]}), 15)

    def test_04_seven_distinct_monetization_models_in_scope(self):
        self.assertEqual({x["model"] for x in self.registry["offers"]}, MOD.MODELS)

    def test_05_11_inquiry_definitions(self):
        self.assertEqual(self.report["inquiry_candidates_source_only"], 11)

    def test_06_free_tool_is_separate_from_paid_catalogue(self):
        self.assertEqual(self.report["free_acquisition_candidates_source_only"], 1)

    def test_07_books_games_bot_subscriptions_blocked(self):
        self.assertEqual(self.report["release_blocked_offers"], 3)
        by_id = {x["offer_id"]: x for x in self.registry["offers"]}
        for key in ("digital_publications", "game_license", "bot_subscription"):
            self.assertEqual(by_id[key]["stage"], "release_blocked")

    def test_08_every_source_file_exists_and_is_regular(self):
        self.assertEqual(self.report["repository_source_verified_count"], 15)

    def test_09_every_offer_has_minimum_qualification(self):
        self.assertTrue(all(len(x["required_inputs"]) >= 2 for x in self.registry["offers"]))

    def test_10_every_offer_has_deliverable_scope(self):
        self.assertTrue(all(len(x["deliverables"]) >= 2 for x in self.registry["offers"]))

    def test_11_every_offer_has_exclusions(self):
        self.assertTrue(all(x["exclusions"] for x in self.registry["offers"]))

    def test_12_no_owner_approved_price_invented(self):
        self.assertTrue(all(x["price_irr"] is None for x in self.registry["offers"]))

    def test_13_no_checkout_rail_enabled(self):
        self.assertTrue(all(x["payment_enabled"] is False for x in self.registry["offers"]))

    def test_14_no_live_bot_or_public_release_claim(self):
        self.assertTrue(all(x["public_live_verified"] is False for x in self.registry["offers"]))

    def test_15_no_fake_owner_approval(self):
        self.assertTrue(all(x["owner_approved"] is False for x in self.registry["offers"]))

    def test_16_no_fake_delivery_proof(self):
        self.assertTrue(all(x["delivery_verified"] is False for x in self.registry["offers"]))

    def test_17_no_verified_sales_are_assumed(self):
        self.assertIsNone(self.report["purchases_verified_count"])
        self.assertIsNone(self.report["revenue_received_irr"])
        self.assertIsNone(self.report["leads_verified_count"])

    def test_18_dry_inspection_produces_no_transactions(self):
        for k in ("customer_messages_sent", "orders_created", "transactions_created",
                  "cost_committed_irr", "production_files_changed"):
            self.assertEqual(self.report[k], 0)

    def test_19_priority_queue_is_deterministic(self):
        q = self.report["priority_queue"]
        self.assertEqual(q, sorted(q, key=lambda x: (x["band"], x["id"])))

    def test_20_priority_queue_has_exact_count(self):
        self.assertEqual(len(self.report["priority_queue"]), 15)

    def test_21_report_excludes_raw_buyer_details_and_quotes(self):
        serialized = json.dumps(self.report, ensure_ascii=False)
        self.assertNotIn(self.registry["offers"][0]["buyer"], serialized)
        self.assertNotIn(self.registry["offers"][0]["value_proposition"], serialized)
        self.assertNotIn(self.registry["offers"][0]["required_inputs"][0], serialized)

    def test_22_duplicate_offer_ids_are_rejected(self):
        doc = copy.deepcopy(self.registry)
        doc["offers"][1]["offer_id"] = doc["offers"][0]["offer_id"]
        with self.assertRaises(MOD.ContractError):
            MOD.assess(ROOT, doc)

    def test_23_noncanonical_bot_is_rejected(self):
        self.check_block(canonical_bot_id="secondary-trading-bot")

    def test_24_noncanonical_registry_root_is_rejected(self):
        doc = copy.deepcopy(self.registry)
        doc["canonical_bot_id"] = "not_the_one_bot"
        with self.assertRaises(MOD.ContractError):
            MOD.assess(ROOT, doc)

    def test_25_unverified_price_is_rejected(self):
        self.check_block(price_irr=1500000)

    def test_26_payment_rail_activations_are_rejected(self):
        self.check_block(payment_enabled=True)

    def test_27_fake_live_verification_is_rejected(self):
        self.check_block(public_live_verified=True)

    def test_28_unapproved_owner_flag_is_rejected(self):
        self.check_block(owner_approved=True)

    def test_29_fake_delivery_claim_is_rejected(self):
        self.check_block(delivery_verified=True)

    def test_30_directory_traversal_is_rejected(self):
        self.check_block(source_files=["../private/customer.csv"])

    def test_31_absolute_source_path_is_rejected(self):
        self.check_block(source_files=["/etc/passwd"])

    def test_32_missing_source_file_is_rejected(self):
        self.check_block(source_files=["madeup/source_registry.txt"])

    def test_33_symlink_source_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "original.txt").write_text("verified local placeholder")
            (root / "alias.txt").symlink_to(root / "original.txt")
            self.assertFalse(MOD.exists_regular_inside(root, "alias.txt"))

    def test_34_duplicate_json_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / "duplicate.json"
            file.write_text('{"schema":"x","schema":"y"}')
            with self.assertRaises(MOD.ContractError):
                MOD.read_registry(file)

    def test_35_missing_buyer_inputs_are_rejected(self):
        self.check_block(required_inputs=[])

    def test_36_duplicate_deliverables_are_rejected(self):
        self.check_block(deliverables=["An initial findings summary", "An initial findings summary"])

    def test_37_empty_exclusions_are_rejected(self):
        self.check_block(exclusions=[])

    def test_38_malicious_remote_form_action_path_rejected(self):
        self.check_block(intake_path="//evil.example/collector")

    def test_39_malicious_newline_in_path_rejected(self):
        self.check_block(intake_path="/ask-master/\nHost:evil")

    def test_40_unplanned_auto_purchase_stage_rejected(self):
        self.check_block(stage="inquiry_candidate", model="subscription")

    def test_41_free_offer_stage_must_match(self):
        self.check_block(stage="free_acquisition", model="consulting_quote")

    def test_42_priority_boolean_must_not_pass_as_integer(self):
        self.check_block(priority_band=True)

    def test_43_priority_outside_bands_rejected(self):
        self.check_block(priority_band=5)

    def test_44_unknown_contract_field_rejected(self):
        doc = copy.deepcopy(self.registry)
        doc["offers"][0]["fake_verified_revenue"] = 9000000
        with self.assertRaises(MOD.ContractError):
            MOD.assess(ROOT, doc)

    def test_45_too_few_offers_rejected(self):
        doc = copy.deepcopy(self.registry)
        doc["offers"] = doc["offers"][:7]
        with self.assertRaises(MOD.ContractError):
            MOD.assess(ROOT, doc)

    def test_46_no_paid_transaction_assumed_for_free_tool(self):
        offer = next(x for x in self.report["offers"] if x["id"] == "free_wheat_tool")
        self.assertFalse(offer["purchase_allowed"])
        self.assertFalse(offer["payment_available_verified"])

    def test_47_source_disposition_manifest_agrees_on_canonical_bot(self):
        disposition = json.loads((ROOT / "runtime/mojtaba_bot_disposition_sources_v1.json").read_text())
        self.assertEqual(disposition["canonical_bot_id"], MOD.CANONICAL_BOT)

    def test_48_cli_evaluates_real_portfolio_and_prints_json_only(self):
        proc = subprocess.run([sys.executable, "-B", str(SCRIPT)],
                              capture_output=True, text=True, timeout=12)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        row = json.loads(proc.stdout)
        self.assertEqual(row["offer_count"], 15)
        self.assertIsNone(row["revenue_received_irr"])

    def test_49_cli_malformed_registry_fails_closed_without_its_content(self):
        secret = "private-customer-name-dont-log"
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad.json"
            path.write_text("not json " + secret)
            proc = subprocess.run([sys.executable, "-B", str(SCRIPT), "--registry", str(path)],
                                  capture_output=True, text=True, timeout=12)
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn(secret, proc.stdout + proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["status"], "blocked")

    def test_50_full_output_contains_only_canonical_bot(self):
        row = self.report
        self.assertEqual(row["canonical_bot_id"], "mojtaba.bot.ai")
        self.assertTrue(all(x["commercial_release_authorized"] is False for x in row["offers"]))


if __name__ == "__main__":
    unittest.main()
