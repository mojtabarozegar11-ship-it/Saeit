"""Integration QA: order-independent autonomous VPS product manufacturing."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import shutil
import tempfile
import unittest
from unittest import mock
import fcntl

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "saeit_vps_cycle", str(ROOT / "scripts" / "factory_vps_product_cycle.py")
)
cycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cycle)


class FactoryVPSCycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.db = self.home / "factory.db"
        self.recipes = self.home / "product_recipes"
        self.output = self.home / "factory-private"
        shutil.copytree(ROOT / "product_recipes" / "farm_enterprise_economics",
                        self.recipes / "farm_enterprise_economics")
        shutil.copytree(ROOT / "product_recipes" / "water_budget_economics",
                        self.recipes / "water_budget_economics")
        shutil.copytree(ROOT / "product_recipes" / "greenhouse_crop_margin",
                        self.recipes / "greenhouse_crop_margin")
        with sqlite3.connect(str(self.db)) as connection:
            connection.executescript("""
                CREATE TABLE core_product(
                    id INTEGER PRIMARY KEY, title TEXT, product_type TEXT,
                    metadata TEXT, active INTEGER, price TEXT,
                    owner_id INTEGER, knowledge_article_id INTEGER,
                    factory_managed INTEGER
                );
                CREATE TABLE core_factoryrun(id INTEGER PRIMARY KEY, product_id INTEGER, status TEXT);
                CREATE TABLE core_researchproject(id INTEGER PRIMARY KEY, factory_run_id INTEGER);
            """)
            metadata = json.dumps({"factory_state":"needs_research","validation":{
                "outcome":"NEEDS_MORE_EVIDENCE","missing_factors":["sources","QA"]}})
            connection.execute("INSERT INTO core_product VALUES (?,?,?,?,?,?,?,?,?)",
                (1, "Factory Candidate", "digital", metadata, 0, "0", None, None, 1))

    def test_cycle_manufactures_real_product_with_no_order_table(self):
        before = self.db.read_bytes()
        first = cycle.run_cycle(self.db, self.output, self.recipes)
        self.assertEqual(first["status"], "ok")
        self.assertEqual(first["processed"], 1)
        self.assertEqual(first["manufactured"], 3)
        state = json.loads((self.output / "production-state.json").read_text(encoding="utf-8"))
        self.assertFalse(state["depends_on_orders"])
        self.assertEqual(state["built_product_count"], 3)
        self.assertEqual(state["new_or_updated_product_count"],3)
        self.assertEqual(state["unchanged_product_rechecks"],0)
        self.assertEqual(first["new_artifacts"],3)
        self.assertEqual(first["new_distinct_products"],3)
        self.assertEqual(first["updated_existing_versions"],0)
        self.assertEqual(state["truly_new_product_count"],3)
        self.assertEqual(state["updated_existing_product_count"],0)
        self.assertEqual(sorted(state["truly_new_product_ids"]),sorted(state["built_product_recipes"]))
        self.assertEqual(state["api_usage"], "none")
        self.assertEqual(state["token_usage"], 0)
        self.assertTrue(state["artifact_qa_passed"])
        self.assertTrue(state["technical_zip_checks_only"])
        self.assertEqual(state["research_review_candidate_count"], 0)
        self.assertFalse(state["research_evidence_thresholds_satisfied_for_all_scanned"])
        self.assertFalse(state["commercial_quality_review_completed"])
        self.assertFalse(state["publishable_product_count"])
        self.assertTrue((self.output / "digital-products" /
                         "farm_enterprise_economics" /
                         "farm_enterprise_economics-internal-qa.zip").exists())
        self.assertTrue((self.output / "digital-products" /
                         "greenhouse_crop_margin" /
                         "greenhouse_crop_margin-internal-qa.zip").exists())
        self.assertEqual(before, self.db.read_bytes())

    def test_second_cycle_is_safe_and_idempotent(self):
        cycle.run_cycle(self.db, self.output, self.recipes)
        subsequent = cycle.run_cycle(self.db, self.output, self.recipes)
        self.assertEqual(subsequent["status"], "ok")
        self.assertEqual(subsequent["updated"], 0)
        self.assertEqual(subsequent["new_artifacts"],0)
        state=json.loads((self.output/"production-state.json").read_text(encoding="utf8"))
        self.assertEqual(state["new_or_updated_product_count"],0)
        self.assertEqual(state["unchanged_product_rechecks"],3)
        self.assertEqual(state["truly_new_product_count"],0)
        self.assertEqual(state["updated_existing_product_count"],0)
        health=json.loads((self.output/"production-health.json").read_text())
        self.assertEqual(health["new_distinct_product_ids_total"],3)
        self.assertEqual(health["new_distinct_product_ids_this_cycle"],0)

    def test_source_change_counts_update_not_new_product(self):
        cycle.run_cycle(self.db,self.output,self.recipes)
        recipe=self.recipes/"water_budget_economics"
        readme=recipe/"README.md"
        readme.write_text(readme.read_text()+"\\nCorrected private planning guidance.\\n")
        result=cycle.run_cycle(self.db,self.output,self.recipes)
        self.assertEqual(result["new_distinct_products"],0)
        self.assertEqual(result["updated_existing_versions"],1)
        health=json.loads((self.output/"production-health.json").read_text())
        self.assertEqual(health["new_distinct_product_ids_total"],3)
        self.assertEqual(health["updated_existing_product_versions_total"],1)

    def test_cycle_builds_a_recipe_added_after_the_factory_code(self):
        shutil.copytree(ROOT / "product_recipes" / "farm_enterprise_economics",
                        self.recipes / "new_product_family")
        (self.recipes / "new_product_family" / "README.md").write_text(
            "# New Product Family\n", encoding="utf-8")
        result = cycle.run_cycle(self.db, self.output, self.recipes)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["manufactured"], 4)
        self.assertTrue((self.output / "digital-products" / "new_product_family" /
                         "new_product_family-internal-qa.zip").is_file())
        state = json.loads((self.output / "production-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["registered_recipe_count"], 4)
        self.assertEqual(state["token_usage"], 0)

    def test_missing_recipe_stops_without_claiming_production(self):
        with self.assertRaises(RuntimeError):
            cycle.run_cycle(self.db, self.output, self.home / "missing")
        self.assertFalse((self.output / "production-state.json").exists())


if __name__ == "__main__":
    unittest.main()

class FactoryCycleIsolationTests(unittest.TestCase):
    setUp = FactoryVPSCycleTests.setUp
    def test_bounded_cycles_rotate_recipes(self):
        seen = []
        for _ in range(3):
            cycle.run_cycle(self.db, self.output, self.recipes, max_recipes=1)
            state = json.loads((self.output/'production-state.json').read_text())
            seen.extend(state['built_product_recipes'])
        self.assertEqual(len(set(seen)),3)

    def test_invalid_recipe_is_reported_without_stopping_good_products(self):
        (self.recipes/'broken_recipe').mkdir()
        result = cycle.run_cycle(self.db, self.output, self.recipes)
        self.assertEqual(result['status'],'needs_rework')
        self.assertEqual(result['manufactured'],3)
        state = json.loads((self.output/'production-state.json').read_text())
        self.assertEqual(state['recipe_admission_failures'][0]['recipe'],'broken_recipe')
        self.assertFalse(state['artifact_qa_passed'])


class FactorySynthesisIntegrationTests(unittest.TestCase):
    setUp = FactoryVPSCycleTests.setUp

    def test_cli_overlap_is_successful_skip(self):
        self.output.mkdir()
        with (self.output/'.production-cycle.lock').open('a+b') as locked:
            fcntl.flock(locked.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            status=cycle.main(['--db',str(self.db),'--out',str(self.output),
                               '--recipes',str(self.recipes)])
        self.assertEqual(status,0)
        self.assertFalse((self.output/'production-state.json').exists())

    def test_corrupt_manifest_shapes_are_rebuilt_without_false_new_products(self):
        cycle.run_cycle(self.db,self.output,self.recipes)
        manifests=sorted((self.output/'digital-products').glob('*/manufacturing_manifest.json'))
        prior=[json.loads(path.read_text()) for path in manifests]
        malformed=[[],dict(prior[1],qa_measurements=[]),
                   dict(prior[2],qa_measurements=dict(prior[2]['qa_measurements'],successful_tests='many'))]
        for path,bad in zip(manifests,malformed): path.write_text(json.dumps(bad))
        result=cycle.run_cycle(self.db,self.output,self.recipes)
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['manufactured'],3)
        self.assertEqual(result['new_artifacts'],0)
        for path in manifests:
            repaired=json.loads(path.read_text())
            self.assertGreater(repaired['qa_measurements']['successful_tests'],0)

    def test_designer_storage_failure_does_not_stop_existing_products(self):
        self.output.mkdir()
        (self.output/'design-state').write_text('deliberately not a directory')
        result=cycle.run_cycle(self.db,self.output,self.recipes,enable_designer=True)
        self.assertEqual(result['status'],'needs_rework')
        self.assertEqual(result['manufactured'],3)
        state=json.loads((self.output/'production-state.json').read_text())
        self.assertTrue(state['designer_failures'])
        self.assertEqual(len(list((self.output/'digital-products').glob('*/*-internal-qa.zip'))),3)

    def test_unclassified_product_runtime_failure_is_durable_and_isolated(self):
        real_load=cycle.load
        maker=real_load('isolated_maker',ROOT/'scripts/factory_product_maker.py')
        original=maker.manufacture
        def manufacture(recipe,*args,**kwargs):
            if recipe=='farm_enterprise_economics':
                raise RuntimeError('NEW_PRODUCT_FAILURE_CATEGORY')
            return original(recipe,*args,**kwargs)
        def load(name,path):
            return maker if name=='saeit_factory_manufacturer_cycle' else real_load(name,path)
        with mock.patch.object(maker,'manufacture',side_effect=manufacture), mock.patch.object(cycle,'load',side_effect=load):
            result=cycle.run_cycle(self.db,self.output,self.recipes)
        self.assertEqual(result['status'],'needs_rework')
        self.assertEqual(result['manufactured'],2)
        ledger=json.loads((self.output/'qa-rework/farm_enterprise_economics/ledger.json').read_text())
        self.assertIn('NEW_PRODUCT_FAILURE_CATEGORY',ledger['history'][-1]['actual_error_excerpt'])

    def test_missing_generated_tests_are_repaired_before_catalog_admission(self):
        cycle.run_cycle(self.db,self.output,self.recipes,enable_designer=True)
        cycle.run_cycle(self.db,self.output,self.recipes,enable_designer=True)
        generated=next((self.output/'generated-product-recipes').iterdir())
        for file in generated.glob('test_*.py'): file.unlink()
        result=cycle.run_cycle(self.db,self.output,self.recipes,enable_designer=True)
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['registered_recipes'],5)
        self.assertTrue(list(generated.glob('test_*.py')))
        state=json.loads((self.output/'production-state.json').read_text())
        self.assertEqual(len(state['source_recoveries']),1)
        retained=Path(state['source_recoveries'][0]['retained_broken_source'])
        self.assertFalse(list(retained.glob('test_*.py')))

    def test_legacy_compiled_product_evolves_through_actual_manufacturing_cycle(self):
        from tests.test_factory_source_evolution import make_legacy_source
        first=cycle.run_cycle(self.db,self.output,self.recipes,enable_designer=True)
        self.assertEqual(first['new_recipe_count'],1)
        generated=self.output/'generated-product-recipes'
        recipe=next(p.name for p in generated.iterdir() if p.is_dir())
        source=generated/recipe
        make_legacy_source(source)
        maker=cycle.load('legacy_maker_for_upgrade',ROOT/'scripts/factory_product_maker.py')
        previous=maker.manufacture(recipe,generated,self.output/'digital-products')
        self.assertTrue(previous['changed'])
        old_archive=(self.output/'digital-products'/recipe/(recipe+'-internal-qa.zip')).read_bytes()
        cycle_result=cycle.run_cycle(self.db,self.output,self.recipes,enable_designer=True)
        self.assertEqual(cycle_result['status'],'ok')
        state=json.loads((self.output/'production-state.json').read_text())
        improved=state['source_evolutions']
        self.assertEqual(len(improved),1)
        self.assertEqual(improved[0]['recipe'],recipe)
        self.assertEqual(state['genuinely_evolved_source_count'],1)
        self.assertEqual(state['source_evolution_policy'],'bounded_compiler_owned_verified_sources_only')
        self.assertNotEqual((self.output/'digital-products'/recipe/(recipe+'-internal-qa.zip')).read_bytes(),old_archive)
        self.assertTrue(Path(improved[0]['previous_source_retained']).is_dir())
        self.assertGreaterEqual(improved[0]['measured_acceptance']['successful_tests'],5)
        manifest=json.loads((self.output/'digital-products'/recipe/'manufacturing_manifest.json').read_text())
        self.assertEqual(manifest['qa_status'],'passed')
        self.assertFalse(manifest['professional_quality_approved'])
        self.assertFalse(state['publication_locked_until_owner_approval'] is False)

    def test_new_recipe_is_generated_built_and_repaired_without_static_folder(self):
        static_before = sorted(x.name for x in self.recipes.iterdir())
        first = cycle.run_cycle(self.db, self.output, self.recipes, enable_designer=True)
        self.assertEqual(first["registered_recipes"],4)
        self.assertEqual(first["new_recipe_count"],1)
        second = cycle.run_cycle(self.db, self.output, self.recipes, enable_designer=True)
        self.assertEqual(second["registered_recipes"],5)
        self.assertEqual(second["new_recipe_count"],1)
        self.assertEqual(sorted(x.name for x in self.recipes.iterdir()),static_before)
        generated=next((self.output/"generated-product-recipes").iterdir())
        (generated/"calculator.py").write_text("raise RuntimeError('deliberate fault')\n")
        third=cycle.run_cycle(self.db, self.output, self.recipes, enable_designer=True)
        self.assertEqual(third["status"],"ok")
        self.assertEqual(third["new_artifacts"],0)
        state=json.loads((self.output/"production-state.json").read_text())
        self.assertEqual(len(state["source_recoveries"]),1)
        self.assertTrue(Path(state["source_recoveries"][0]["retained_broken_source"]).is_dir())
        ledger=json.loads((self.output/"qa-rework"/generated.name/"ledger.json").read_text())
        self.assertEqual(ledger["current_status"],"technical_qa_pass_only_owner_and_content_review_pending")
        self.assertGreaterEqual(len(ledger["history"]),1)

class ProductionContinuityTests(unittest.TestCase):
    setUp=FactoryVPSCycleTests.setUp

    def test_unavailable_research_database_does_not_stop_independent_manufacturing(self):
        result=cycle.run_cycle(self.home/'unavailable.db',self.output,self.recipes)
        self.assertEqual(result['status'],'needs_rework')
        self.assertEqual(result['manufactured'],3)
        state=json.loads((self.output/'production-state.json').read_text())
        self.assertTrue(state['research_failures'])
        self.assertEqual(state['product_candidates_processed'],0)

    def test_filesystem_failure_in_one_product_is_isolated(self):
        real_load=cycle.load
        maker=real_load('failure_isolation',ROOT/'scripts/factory_product_maker.py')
        original=maker.manufacture
        def manufacture(recipe,*args,**kwargs):
            if recipe=='farm_enterprise_economics':raise OSError('injected write failure')
            return original(recipe,*args,**kwargs)
        def load(name,path):
            return maker if name=='saeit_factory_manufacturer_cycle' else real_load(name,path)
        with mock.patch.object(maker,'manufacture',side_effect=manufacture),mock.patch.object(cycle,'load',side_effect=load):
            result=cycle.run_cycle(self.db,self.output,self.recipes)
        self.assertEqual(result['manufactured'],2)
        self.assertEqual(result['failed'],1)
        self.assertTrue((self.output/'qa-rework/farm_enterprise_economics/ledger.json').is_file())

    def test_admission_failures_enter_durable_rework(self):
        (self.recipes/'broken_recipe').mkdir()
        cycle.run_cycle(self.db,self.output,self.recipes)
        data=json.loads((self.output/'qa-rework/broken_recipe/ledger.json').read_text())
        self.assertFalse(data['public_sale_allowed'])
        self.assertEqual(len(data['history']),1)

    def test_health_distinguishes_rechecks_from_new_products_and_tracks_recovery(self):
        cycle.run_cycle(self.db,self.output,self.recipes)
        cycle.run_cycle(self.db,self.output,self.recipes)
        path=self.output/'production-health.json';data=json.loads(path.read_text())
        self.assertEqual(data['completed_cycles'],2)
        self.assertEqual(data['new_or_updated_artifacts_total'],3)
        self.assertEqual(data['new_or_updated_artifacts_this_cycle'],0)
        self.assertIsNotNone(data['last_healthy_cycle_at_utc'])
        cycle.run_cycle(self.home/'missing.db',self.output,self.recipes)
        data=json.loads(path.read_text());self.assertEqual(data['consecutive_degraded_cycles'],1)
        cycle.run_cycle(self.db,self.output,self.recipes)
        self.assertEqual(json.loads(path.read_text())['consecutive_degraded_cycles'],0)

    def test_design_capacity_must_be_bounded(self):
        for bad in (0,21,True,"6"):
            with self.assertRaisesRegex(ValueError,"DESIGN_CAPACITY_INVALID"):
                cycle.run_cycle(self.db,self.output,self.recipes,design_capacity=bad)

    def test_direct_api_rejects_invalid_limits(self):
        for kwargs in ({'max_products':True},{'max_products':0},{'max_recipes':0},{'max_recipes':True}):
            with self.assertRaisesRegex(ValueError,'BOUNDED_LIMIT'):cycle.run_cycle(self.db,self.output,self.recipes,**kwargs)

    def test_deferred_design_failure_is_not_reported_as_healthy(self):
        real_load=cycle.load
        designer=real_load('deferred_designer',ROOT/'scripts/factory_recipe_designer.py')
        result={'new_recipes':0,'intake_failures':[],'rework':[], 'deferred_rework_requests':1}
        def load(name,path):
            return designer if name=='saeit_factory_recipe_designer' else real_load(name,path)
        with mock.patch.object(designer,'cycle',return_value=result),mock.patch.object(cycle,'load',side_effect=load):
            state=cycle.run_cycle(self.db,self.output,self.recipes,enable_designer=True)
        self.assertEqual(state['status'],'needs_rework')
        self.assertEqual(state['manufactured'],3)
        self.assertTrue(json.loads((self.output/'production-health.json').read_text())['unfinished_rework_requires_attention'])

    def test_high_level_internal_needs_feed_real_new_product_builds(self):
        novel=0
        actual_cycles=[]
        for _ in range(6):
            result=cycle.run_cycle(self.db,self.output,self.recipes,enable_designer=True,
                                   enable_design_intake=True,design_capacity=6)
            novel+=result['new_artifacts']
            snapshot=json.loads((self.output/'production-state.json').read_text())
            latest_failures=[]
            for item in snapshot.get("quality_failures_this_cycle",[]):
                ledger_file=self.output/'qa-rework'/item['recipe']/'ledger.json'
                record=json.loads(ledger_file.read_text()) if ledger_file.is_file() else {}
                history=record.get('history',[])
                latest_failures.append(dict(item, actual_error_excerpt=(
                    history[-1].get('actual_error_excerpt') if history else None)))
            actual_cycles.append({"new":result["new_artifacts"],
                                  "built":result["manufactured"],
                                  "failures":latest_failures,
                                  "designer":snapshot.get("designer_failures"),
                                  "customer":snapshot.get("real_customer_zip_checks_passed")})
        status=json.loads((self.output/'engineering-intake/production-results.json').read_text())
        source_receipts=[]
        for path in (self.output/'engineering-intake').glob('*.json'):
            if len(path.stem)!=64: continue
            receipt=json.loads(path.read_text())
            source_receipts.append({'id':receipt.get('source_id'),
                                    'status':receipt.get('status'),
                                    'reason':receipt.get('reason')})
        designer_state=json.loads((self.output/'designer-state.json').read_text())
        deferred=[]
        for path in (self.output/'design-state').glob('*.json'):
            item=json.loads(path.read_text())
            if item.get('status')=='design_rework_required':
                deferred.append({'request':item.get('request_file'),
                                 'reason':item.get('reason')})
        self.assertLessEqual(status['technical_prototypes'],5,
                             json.dumps({'sources':source_receipts,'deferred':deferred,
                                         'designer_pending':designer_state.get('pending_requests'),
                                         'designer_rework':designer_state.get('rework')},sort_keys=True))
        self.assertLessEqual(status['functional_products'],5)
        slots=json.loads((self.output/'quality-excellence/product-flow/active-slots/current.json').read_text())
        self.assertEqual(slots['line_id'],41)
        self.assertEqual(slots['capacity'],1)
        self.assertEqual(len(slots['active']),1)
        self.assertEqual(novel,5,json.dumps(actual_cycles,sort_keys=True))
        replay=cycle.run_cycle(self.db,self.output,self.recipes,enable_designer=True,
                               enable_design_intake=True,design_capacity=6)
        self.assertEqual(replay['new_artifacts'],0)
        for receipt in (self.output/'engineering-intake').glob('*.json'):
            item=json.loads(receipt.read_text())
            if item.get('status')=='technical_prototype_built':
                self.assertFalse(item['build50_verified'])
                self.assertFalse(item['commercial_release'])
