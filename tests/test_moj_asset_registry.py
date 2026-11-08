"""Offline specification and anti-misrepresentation checks for 51 asset plans."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from copy import deepcopy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from moj_asset_registry import (  # noqa: E402
    MAX_SERIES_SUPPLY, MIN_SERIES_SUPPLY, MOJONER_SUPPLY,
    evm_candidate_sources, export_bundle, f41_shasta_candidate_specs,
    generate_program, ord_etching_fragment, series_supply,
    mojoner_rune_name_length_gate,
    validate_program, verify_bundle,
)


class AssetRegistryTests(unittest.TestCase):
    def test_unknown_claim_fields_are_rejected_in_program_and_assets(self):
        self.rejects("unexpected_program_fields", lambda p: p.update(exchange_listing_verified=True))
        self.rejects("unexpected_asset_fields", lambda p: p["assets"][0].update(onchain_tx_id="fake"))
        self.rejects("unexpected_asset_fields", lambda p: p["assets"][1].update(liquidity_funded=True))

    def test_program_purpose_cannot_claim_onchain_issuance(self):
        self.rejects("invalid_program_purpose", lambda p: p.update(purpose="mainnet_issuance"))

    def setUp(self):
        self.program = generate_program()

    def rejects(self, message, mutation):
        candidate = deepcopy(self.program)
        mutation(candidate)
        with self.assertRaisesRegex(ValueError, message):
            validate_program(candidate)

    def test_exactly_51_unique_assets(self):
        self.assertEqual(len(self.program["assets"]), 51)
        self.assertEqual(len({x["id"] for x in self.program["assets"]}), 51)

    def test_mojoner_bitcoin_supply_is_exact(self):
        self.assertEqual(int(self.program["assets"][0]["supply_tokens"]), MOJONER_SUPPLY)

    def test_mojoner_display_name_is_immutable_in_candidate(self):
        self.rejects("bitcoin_runes_spec_mismatch", lambda p: p["assets"][0].update(name="Imposter"))

    def test_mojoner_seven_letter_length_unlock_is_not_availability(self):
        before = mojoner_rune_name_length_gate(944_999)
        after = mojoner_rune_name_length_gate(945_000)
        self.assertEqual(after["full_length_unlock_height"], 945_000)
        self.assertFalse(before["length_eligible"])
        self.assertTrue(after["length_eligible"])
        self.assertFalse(after["name_availability_verified"])
        self.assertFalse(after["commitment_confirmations_verified"])
        self.assertFalse(after["mainnet_authorized"])

    def test_mojoner_length_gate_rejects_unverified_height_types(self):
        for bad in (True, 945_000.0, "945000", -1, None):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "verified_bitcoin_height_required"):
                    mojoner_rune_name_length_gate(bad)

    def test_bitcoin_runes_etching_has_no_unintended_open_mint(self):
        self.assertEqual(self.program["assets"][0]["runes_etching_proposal"], {
            "premine": str(MOJONER_SUPPLY), "supply": str(MOJONER_SUPPLY),
            "terms": None})

    def test_minimum_and_maximum_series_supply_inclusive(self):
        self.assertEqual(series_supply(1), MIN_SERIES_SUPPLY)
        self.assertEqual(series_supply(50), MAX_SERIES_SUPPLY)

    def test_all_50_supplies_are_distinct_in_range(self):
        supplies = [int(asset["supply_tokens"]) for asset in self.program["assets"][1:]]
        self.assertEqual(len(supplies), len(set(supplies)))
        self.assertTrue(all(MIN_SERIES_SUPPLY <= x <= MAX_SERIES_SUPPLY for x in supplies))

    def test_supply_generator_rejects_invalid_indexes(self):
        for value in [0, -1, 51, True, 1.0, "1"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                series_supply(value)

    def test_duplicate_asset_id_is_rejected(self):
        self.rejects("asset_identifier_collision", lambda p: p["assets"][2].update(id="moj1"))

    def test_duplicate_ticker_is_rejected(self):
        self.rejects("asset_identifier_collision", lambda p: p["assets"][3].update(symbol_candidate="MOJ1"))

    def test_asset_id_and_symbol_must_be_plain_normalized_strings(self):
        for field, invalid in (
            ("id", ["moj1"]), ("id", None), ("id", "moj1 "),
            ("symbol_candidate", ["MOJ1"]), ("symbol_candidate", True),
            ("symbol_candidate", "MOJ 1"),
        ):
            with self.subTest(field=field, invalid=invalid):
                self.rejects(
                    "asset_identifier_collision",
                    lambda p, field=field, invalid=invalid: p["assets"][1].update({field: invalid}),
                )

    def test_non_mapping_asset_records_are_rejected_predictably(self):
        for invalid in (None, "moj1", ["moj1"], 42):
            with self.subTest(invalid=invalid):
                self.rejects(
                    "invalid_asset_record",
                    lambda p, invalid=invalid: p["assets"].__setitem__(1, invalid),
                )


    def test_missing_asset_is_rejected(self):
        self.rejects("wrong_asset_count", lambda p: p["assets"].pop())

    def test_extra_asset_is_rejected(self):
        self.rejects("wrong_asset_count", lambda p: p["assets"].append({"id": "moj51"}))

    def test_bitcoin_supply_tamper_is_rejected(self):
        self.rejects("bitcoin_runes_spec_mismatch", lambda p: p["assets"][0].update(supply_tokens="24567857"))

    def test_bitcoin_premine_mismatch_is_rejected(self):
        self.rejects("runes_supply_formula_mismatch", lambda p: p["assets"][0]["runes_etching_proposal"].update(premine="24567855"))

    def test_open_mint_terms_are_forbidden(self):
        self.rejects("runes_supply_formula_mismatch", lambda p: p["assets"][0]["runes_etching_proposal"].update(terms={"amount": "1", "cap": 1}))

    def test_ord_fragment_omits_open_mint_terms(self):
        fragment = ord_etching_fragment(self.program)
        self.assertIn("  premine: 24567856\n", fragment)
        self.assertIn("  supply: 24567856\n", fragment)
        self.assertIn("ord wallet batch YAML requires both supply and premine", fragment)
        self.assertIn("name commitment", fragment)
        self.assertNotIn("  terms:", fragment)
        self.assertNotIn("wallet broadcast", fragment)

    def test_fractional_bitcoin_units_are_rejected(self):
        self.rejects("bitcoin_runes_spec_mismatch", lambda p: p["assets"][0].update(divisibility_proposal=8))

    def test_series_oversupply_is_rejected(self):
        self.rejects("series_asset_spec_mismatch", lambda p: p["assets"][7].update(supply_tokens="10000000000001"))

    def test_series_negative_supply_is_rejected(self):
        self.rejects("supply_must_be_positive_integer_string", lambda p: p["assets"][8].update(supply_tokens="-1"))

    def test_series_float_supply_is_rejected(self):
        self.rejects("supply_must_be_positive_integer_string", lambda p: p["assets"][9].update(supply_tokens=1e12))

    def test_unselected_non_bitcoin_network_remains_unselected(self):
        self.rejects("series_asset_spec_mismatch", lambda p: p["assets"][1].update(network="ethereum"))

    def test_false_onchain_claim_is_rejected(self):
        self.rejects("unverified_issuance_or_income_claim", lambda p: p["assets"][0].update(issuance_state="issued"))

    def test_mainnet_activation_is_rejected(self):
        self.rejects("unverified_issuance_or_income_claim", lambda p: p["assets"][4].update(mainnet_authorized=True))

    def test_unverified_sales_are_rejected(self):
        self.rejects("unverified_issuance_or_income_claim", lambda p: p.update(verified_income="1000"))

    def test_nonzero_transaction_count_is_rejected(self):
        self.rejects("unverified_issuance_or_income_claim", lambda p: p.update(transactions_broadcast=1))

    def test_fee_gate_cannot_be_silently_opened(self):
        self.rejects("unauthorized_release_gate", lambda p: p["gates"].update(owner_fee_approval=True))

    def test_f41_existing_builder_specs_are_compatible(self):
        specs = f41_shasta_candidate_specs(self.program)
        self.assertEqual(len(specs), 50)
        self.assertNotIn("mojoner", specs)
        from factory_f41_token_builder_v2 import FIELDS, SCHEMA, spec_read
        with tempfile.TemporaryDirectory() as directory:
            for asset_id, spec in specs.items():
                self.assertEqual(set(spec), FIELDS)
                self.assertEqual(spec["schema"], SCHEMA)
                path = Path(directory) / f"{asset_id}.json"
                path.write_text(json.dumps(spec), encoding="utf-8")
                parsed, units = spec_read(path)
                self.assertEqual(parsed["symbol"], asset_id.upper())
                self.assertEqual(units, int(parsed["supply_tokens"]) * 10**18)

    def test_fifty_evm_sources_are_fixed_supply_and_distinct(self):
        sources = evm_candidate_sources(self.program)
        self.assertEqual(len(sources), 50)
        for asset in self.program["assets"][1:]:
            code = sources[asset["id"]]
            units = int(asset["supply_tokens"]) * 10**18
            self.assertIn(f'_mint(initialHolder, {units});', code)
            self.assertIn(f'ERC20("{asset["name"]}", "{asset["symbol_candidate"]}")', code)
            self.assertIn("zero_initial_holder", code)
            self.assertNotIn("function mint", code)
            self.assertNotIn("tx.origin", code)

    def test_all_50_contract_declarations_are_unique_when_compiled_together(self):
        sources = evm_candidate_sources(self.program)
        declarations = []
        for number in range(1, 51):
            code = sources[f"moj{number}"]
            expected = f"Moj{number}FixedSupply"
            self.assertIn(f"contract {expected} is ERC20 {{", code)
            declarations.append(expected)
        self.assertEqual(len(declarations), len(set(declarations)))
        self.assertNotIn("contract MojFixedSupply is ERC20", "\n".join(sources.values()))

    def test_generated_erc20_has_no_second_mint_or_admin_key(self):
        for number, code in enumerate(evm_candidate_sources(self.program).values(), 1):
            with self.subTest(number=number):
                self.assertEqual(code.count("_mint("), 1)
                self.assertNotIn("Ownable", code)
                self.assertNotIn("delegatecall", code)
                self.assertNotIn("function transferOwnership", code)
                self.assertIn("require(initialHolder != address(0)", code)

    def test_mojoner_is_never_generated_as_erc20(self):
        self.assertNotIn("mojoner", evm_candidate_sources(self.program))

    def test_bundle_export_writes_102_offline_documents_and_checksums(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "new"
            receipt = export_bundle(self.program, target)
            self.assertEqual(receipt["assets"], 51)
            self.assertEqual(receipt["offline_files"], 103)
            self.assertFalse(receipt["on_chain_issuance"])
            self.assertEqual(len(list((target / "f41-shasta").glob("moj*.json"))), 50)
            self.assertEqual(len(list(target.glob("evm-candidates/moj*/contracts/Moj*FixedSupply.sol"))), 50)
            for n in range(1, 51):
                self.assertTrue((target / f"evm-candidates/moj{n}/contracts/Moj{n}FixedSupply.sol").is_file())
            self.assertTrue((target / "bitcoin-runes/mojoner-etching-fragment.yaml").is_file())
            self.assertEqual(len(json.loads((target / "SHA256SUMS.json").read_text())), 102)
            self.assertEqual(verify_bundle(self.program, target)["offline_files"], 103)
            with self.assertRaisesRegex(ValueError, "output_must_be_new_directory"):
                export_bundle(self.program, target)

    def test_bundle_verifier_rejects_tampered_evm_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "new"
            export_bundle(self.program, target)
            source = target / "evm-candidates/moj1/contracts/Moj1FixedSupply.sol"
            source.write_text(source.read_text() + "// changed\n")
            with self.assertRaisesRegex(ValueError, "bundle_content_mismatch"):
                verify_bundle(self.program, target)

    def test_bundle_verifier_rejects_extra_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "new"
            export_bundle(self.program, target)
            (target / "unexpected.txt").write_text("extra")
            with self.assertRaisesRegex(ValueError, "bundle_inventory_mismatch"):
                verify_bundle(self.program, target)


    def test_bundle_verifier_rejects_unexpected_empty_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "new"
            export_bundle(self.program, target)
            (target / "hidden-contents").mkdir()
            with self.assertRaisesRegex(ValueError, "bundle_unexpected_directory"):
                verify_bundle(self.program, target)


if __name__ == "__main__":
    unittest.main()
