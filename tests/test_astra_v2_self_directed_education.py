"""Continuous, order-free case production: independent arithmetic + VPS-style tick."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("astra_autonomous_casework_tests",
    ROOT/"scripts"/"astra_v2_self_directed_education.py")
casework=importlib.util.module_from_spec(s)
s.loader.exec_module(casework)
p=importlib.util.spec_from_file_location("astra_private_tick_case_tests",
    ROOT/"scripts"/"astra_v2_private_pipeline.py")
pipeline=importlib.util.module_from_spec(p)
p.loader.exec_module(pipeline)


class SelfDirectedWorkTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=pipeline.safe_root(Path(t.name)/"private")

    def test_four_distinct_finance_education_methods_in_rotation(self):
        methods=set()
        for hour in range(1000,1004):
            case=casework.case_for_hour(hour)
            methods.add(case["subject"])
            self.assertEqual(len(case["questions"]),3)
            self.assertGreaterEqual(len(case["answers"]),3)
            self.assertIs(case["customer_order_required"],False)
            self.assertIs(case["actual_market_data"],False)
            self.assertIs(case["publication_allowed"],False)
        self.assertEqual(methods,set(casework.KINDS))

    def test_unsupported_hour_rejected_without_file(self):
        for x in (-1,True,"2026",10_000_001):
            with self.subTest(value=x):
                with self.assertRaises(ValueError):
                    casework.case_for_hour(x)

    def test_npv_answers_are_independently_reproducible(self):
        h=4_000
        item=casework.case_for_hour(h)
        self.assertEqual(item["subject"],"capital_budgeting")
        i=item["givens"];r=Decimal(i["discount_rate_pct"])/100
        annual=Decimal(i["annual_cash_after_costs"])
        initial=Decimal(i["investment_now"])
        exact=-initial+sum(annual/((1+r)**year)
                           for year in range(1,i["years"]+1))
        self.assertEqual(Decimal(item["answers"]["base_npv"]),
                         exact.quantize(Decimal("0.01")))

    def test_procurement_educational_answer_is_independent(self):
        item=casework.case_for_hour(4_001)
        self.assertEqual(item["subject"],"input_procurement")
        data=item["givens"]
        for k in ("a","b"):
            o=data["quote_"+k]
            gross=Decimal(data["net_usable_units"])/(1-Decimal(o["waste_pct"])/100)
            total=gross*Decimal(o["price_per_gross_unit"])+Decimal(o["freight"])
            self.assertEqual(Decimal(item["answers"]["delivered_total_"+k]),
                             total.quantize(Decimal(".01")))

    def test_break_even_math_is_correct(self):
        item=casework.case_for_hour(4_002)
        self.assertEqual(item["subject"],"break_even")
        d=item["givens"]
        cm=Decimal(d["price_per_unit"])-Decimal(d["variable_cost_per_unit"])
        self.assertEqual(Decimal(item["answers"]["contribution_per_unit"]),cm)
        self.assertEqual(Decimal(item["answers"]["planned_profit"]),
                         Decimal(d["planned_units"])*cm-Decimal(d["fixed_cost"]))

    def test_irrigation_constraints_are_satisfied(self):
        item=casework.case_for_hour(4_003)
        self.assertEqual(item["subject"],"irrigation_allocation")
        d=item["givens"];a=item["answers"]
        possible=Decimal(d["available_water_m3"])/Decimal(d["hypothetical_water_m3_per_hectare"])
        self.assertEqual(Decimal(a["usable_hectares"]),
                         min(possible,Decimal(d["available_land_hectares"])).quantize(Decimal(".01")))

    def test_one_private_edition_has_distinct_solution_and_self_test(self):
        result=casework.build_hour(self.root,5000)
        self.assertEqual(result["status"],"PRIVATE_CASE_BUILT")
        self.assertTrue(result["new_private_educational_edition"])
        self.assertFalse(result["sale_ready"])
        packs=list((self.root/"autonomous_education").glob("case-*.zip"))
        self.assertEqual(len(packs),1)
        with zipfile.ZipFile(packs[0]) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(len(z.namelist()),4)
            data=json.loads(z.read("astra_case/CASE.json"))
            self.assertEqual(data["edition_number"],5000)
            self.assertIn(b"FICTIONAL EDUCATIONAL",z.read("astra_case/CASE_STUDY.md"))
            self.assertIn(b"Independently recalculated",z.read("astra_case/ANSWER_KEY.md"))
        self.assertEqual(packs[0].stat().st_mode&0o777,0o600)

    def test_repeated_hour_is_idempotent_but_next_hour_new_case(self):
        first=casework.build_hour(self.root,10_000)
        again=casework.build_hour(self.root,10_000)
        next_hour=casework.build_hour(self.root,10_001)
        self.assertEqual(first["status"],"PRIVATE_CASE_BUILT")
        self.assertEqual(again["status"],"UNCHANGED")
        self.assertFalse(again["new_private_educational_edition"])
        self.assertEqual(next_hour["status"],"PRIVATE_CASE_BUILT")
        self.assertNotEqual(first["sha256"],next_hour["sha256"])
        self.assertEqual(len(list((self.root/"autonomous_education").glob("case-*.zip"))),2)

    def test_cases_are_independent_of_orders_and_inbox(self):
        self.assertFalse((self.root/"incoming").exists())
        output=pipeline.tick(self.root)
        self.assertEqual(output["status"],"NO_ELIGIBLE_WORK")
        self.assertIn(output["autonomous_education"]["status"],("PRIVATE_CASE_BUILT","UNCHANGED"))
        self.assertEqual(output["new_products"],0)
        current=pipeline.status(self.root)
        self.assertEqual(current["self_directed_private_educational_editions"],1)
        self.assertEqual(current["distinct_private_product_families"],0)
        self.assertEqual(current["published_products"],0)

    def test_two_ticks_in_same_hour_do_not_falsify_new_production(self):
        one=pipeline.tick(self.root)
        two=pipeline.tick(self.root)
        self.assertEqual(one["autonomous_education"]["status"],"PRIVATE_CASE_BUILT")
        self.assertEqual(two["autonomous_education"]["status"],"UNCHANGED")
        self.assertEqual(pipeline.status(self.root)["self_directed_private_educational_editions"],1)

    def test_resource_limit_halts_cleanly_without_making_false_count(self):
        old=casework.MAX_CASE_BYTES
        try:
            casework.MAX_CASE_BYTES=0
            outcome=casework.build_hour(self.root,12001)
            self.assertEqual(outcome["status"],"RESOURCE_REVIEW_REQUIRED")
            self.assertFalse(outcome["new_private_educational_edition"])
        finally:
            casework.MAX_CASE_BYTES=old

    def test_unsafe_output_symlink_fails_closed(self):
        with tempfile.TemporaryDirectory() as other:
            (self.root/"autonomous_education").symlink_to(other)
            with self.assertRaises(ValueError):
                casework.build_hour(self.root,1011)

    def test_manual_standalone_demo_produces_then_deduplicates(self):
        proc=subprocess.run([sys.executable,str(ROOT/"scripts"/"astra_v2_self_directed_education.py"),
                            "--demo"],capture_output=True,text=True,timeout=15)
        self.assertEqual(proc.returncode,0,proc.stderr)
        lines=[json.loads(s) for s in proc.stdout.splitlines() if s.startswith("{")]
        self.assertEqual([e["status"] for e in lines],["PRIVATE_CASE_BUILT","UNCHANGED"])

    def test_bundle_self_test_runs_without_builder_source(self):
        casework.build_hour(self.root,3333)
        with tempfile.TemporaryDirectory() as path:
            pack=next((self.root/"autonomous_education").glob("case-*.zip"))
            with zipfile.ZipFile(pack) as z:z.extractall(path)
            proc=subprocess.run([sys.executable,str(Path(path)/"astra_case"/"self_test.py")],
                                capture_output=True,text=True,timeout=10)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertIn("ASTRA_EDUCATIONAL_CASE_SELFTEST=PASS",proc.stdout)

    def test_simulated_48_hour_no_order_soak_has_real_unique_qa_editions(self):
        # Synthetic accelerated model only; does not claim 48h live uptime.
        ids=set()
        paths=[]
        for hour in range(21_000,21_048):
            result=casework.build_hour(self.root,hour)
            self.assertEqual(result["status"],"PRIVATE_CASE_BUILT",result)
            self.assertTrue(result["new_private_educational_edition"])
            self.assertNotIn(result["sha256"],ids)
            ids.add(result["sha256"])
            cases=list((self.root/"autonomous_education").glob(
                "case-"+str(hour).zfill(8)+"-*.zip"))
            self.assertEqual(len(cases),1)
            paths.append(cases[0])
        self.assertEqual(len(ids),48)
        self.assertEqual(len(paths),48)
        for f in paths:
            with zipfile.ZipFile(f) as z:
                self.assertIsNone(z.testzip())
                case=json.loads(z.read("astra_case/CASE.json"))
                self.assertFalse(case["publication_allowed"])
                self.assertFalse(case["actual_market_data"])
                self.assertFalse(case["commercial_quality_assessed"])
        self.assertEqual(casework.build_hour(self.root,21_047)["status"],"UNCHANGED")
        self.assertEqual(len(list((self.root/"autonomous_education").glob("case-*.zip"))),48)

    def test_bounded_retention_preserves_protected_cases_and_keeps_producing(self):
        old_count,old_age=(casework.MAX_RETAINED_EDUCATIONAL_CASES,
                           casework.MIN_PROTECTED_AGE_HOURS)
        casework.MAX_RETAINED_EDUCATIONAL_CASES=3
        casework.MIN_PROTECTED_AGE_HOURS=2
        try:
            for hour in range(1100,1108):
                item=casework.build_hour(self.root,hour)
                self.assertEqual(item["status"],"PRIVATE_CASE_BUILT",item)
                self.assertLessEqual(len(list(
                    (self.root/"autonomous_education").glob("case-*.zip"))),3)
            packs=list((self.root/"autonomous_education").glob("case-*.zip"))
            self.assertEqual(len(packs),3)
            observed=sorted(int(p.name.split("-")[1]) for p in packs)
            self.assertEqual(observed,[1105,1106,1107])
            self.assertEqual(casework.build_hour(self.root,1107)["status"],"UNCHANGED")
        finally:
            casework.MAX_RETAINED_EDUCATIONAL_CASES=old_count
            casework.MIN_PROTECTED_AGE_HOURS=old_age

    def test_invalid_generated_edition_is_not_silently_counted_as_unchanged(self):
        result=casework.build_hour(self.root,5400)
        self.assertEqual(result["status"],"PRIVATE_CASE_BUILT")
        file=next((self.root/"autonomous_education").glob("case-*.zip"))
        original=file.read_bytes()
        file.write_bytes(b"tampered-not-a-zip")
        with self.assertRaises((ValueError,zipfile.BadZipFile)):
            casework.build_hour(self.root,5400)
        self.assertEqual(file.read_bytes(),b"tampered-not-a-zip")
        self.assertNotEqual(file.read_bytes(),original)

    def test_foreign_archive_survives_synthetic_retention(self):
        old_count,old_age=(casework.MAX_RETAINED_EDUCATIONAL_CASES,
                           casework.MIN_PROTECTED_AGE_HOURS)
        casework.MAX_RETAINED_EDUCATIONAL_CASES=2
        casework.MIN_PROTECTED_AGE_HOURS=1
        try:
            casework.build_hour(self.root,3000)
            folder=self.root/"autonomous_education"
            foreign=folder/"case-00000001-deadbeefdeadbeef.zip"
            foreign.write_bytes(b"unrecognized-third-party-data")
            second=folder/"case-00000002-deadbeefdeadbeef.zip"
            second.write_bytes(b"second-foreign-artifact")
            result=casework.build_hour(self.root,3001)
            self.assertEqual(result["status"],"RESOURCE_REVIEW_REQUIRED")
            self.assertTrue(foreign.exists())
            self.assertEqual(foreign.read_bytes(),b"unrecognized-third-party-data")
        finally:
            casework.MAX_RETAINED_EDUCATIONAL_CASES=old_count
            casework.MIN_PROTECTED_AGE_HOURS=old_age

    def test_unknown_private_files_are_never_deleted_during_rotation(self):
        old_count,old_age=(casework.MAX_RETAINED_EDUCATIONAL_CASES,
                           casework.MIN_PROTECTED_AGE_HOURS)
        casework.MAX_RETAINED_EDUCATIONAL_CASES=2
        casework.MIN_PROTECTED_AGE_HOURS=1
        try:
            casework.build_hour(self.root,7000)
            folder=self.root/"autonomous_education"
            secret=folder/"somebodys-private-research.txt"
            secret.write_text("DO NOT TOUCH")
            casework.build_hour(self.root,7001)
            self.assertEqual(casework.build_hour(self.root,7002)["status"],
                             "PRIVATE_CASE_BUILT")
            self.assertTrue(secret.is_file())
            self.assertEqual(secret.read_text(),"DO NOT TOUCH")
        finally:
            casework.MAX_RETAINED_EDUCATIONAL_CASES=old_count
            casework.MIN_PROTECTED_AGE_HOURS=old_age

    def test_case_version_is_stable_across_restart(self):
        a=casework.case_for_hour(29993)
        b=casework.case_for_hour(29993)
        self.assertEqual(a,b)
        self.assertNotIn("verified customer",json.dumps(a).lower())


if __name__=="__main__":
    unittest.main()
