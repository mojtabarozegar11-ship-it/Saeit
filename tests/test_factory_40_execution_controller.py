"""Full 40-family admission, not a simulation of 40 completed producers."""
import importlib.util
from pathlib import Path
import json
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[1]
SCRIPTS=REPO/'scripts'
REGISTRY=REPO/'factory_config/forty_families.json'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,str(path))
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
ctrl=load('tested_40_execution_controller',SCRIPTS/'factory_40_execution_controller.py')
master=load('tested_40_master',SCRIPTS/'factory_40_family_master.py')
bridge=load('tested_40_bridge',SCRIPTS/'factory_build50_family_bridge.py')
proto=load('tested_40_protocol',SCRIPTS/'factory_build_50.py')
class RealFamilyAdmission(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.profiles=master.registry_valid(ctrl.read(REGISTRY))
    def test_all_families_have_specific_adapter_and_true_blocker(self):
        ledger=bridge.inventory(self.root,REGISTRY,proto,master)
        rows,totals=ctrl.plan_state(ledger,self.profiles)
        self.assertEqual(len(rows),40)
        self.assertEqual(len(set(x['producer_adapter'] for x in rows)),40)
        self.assertEqual(totals['registered'],40)
        self.assertEqual(totals['families_with_real_50_stage_products'],0)
        self.assertEqual(totals['families_with_pilot_queued'],11)
        self.assertEqual(totals['families_blocked_no_pilot_or_producer'],29)
        self.assertTrue(all(not x['commercial_release_allowed'] for x in rows))
        self.assertTrue(all(x['required_work_packages']==48 for x in rows))
    def test_validated_pilot_is_not_50_stage_or_commercial_release(self):
        ledger=bridge.inventory(self.root,REGISTRY,proto,master)
        ledger['families'][9]['technical_pilot_count']=1
        rows,totals=ctrl.plan_state(ledger,self.profiles)
        self.assertEqual(rows[9]['family_id'],'F10')
        self.assertEqual(rows[9]['operational_state'],'verified_technical_pilot_only')
        self.assertEqual(rows[9]['completed_50_stage_products'],0)
        self.assertEqual(totals['families_with_real_50_stage_products'],0)
        self.assertEqual(totals['families_with_verified_pilots_only'],1)
    def test_50_stage_only_when_proof_provided(self):
        ledger=bridge.inventory(self.root,REGISTRY,proto,master)
        ledger['families'][26]['technical_50_stage_completed']=1
        rows,totals=ctrl.plan_state(ledger,self.profiles)
        self.assertEqual(rows[26]['operational_state'],'real_50_stage_product_exists')
        self.assertEqual(totals['families_with_real_50_stage_products'],1)
        self.assertEqual(totals['families_without_validated_50_stage_executor'],39)
        self.assertFalse(rows[26]['commercial_release_allowed'])
    def test_inspect_only_is_actual_readback_and_no_product_forgery(self):
        report=ctrl.run(self.root,REGISTRY,SCRIPTS,pilot=False)
        self.assertEqual(report['counts']['registered'],40)
        self.assertEqual(report['counts']['families_with_real_50_stage_products'],0)
        self.assertFalse(report['store_publication_enabled'])
        self.assertFalse(report['warehouse_promotion_enabled'])
        self.assertEqual(report['customer_orders_created'],0)
        self.assertTrue((self.root/'production-family-management/forty-execution-dashboard.json').is_file())
    def test_incomplete_registered_families_fail_closed(self):
        item=bridge.inventory(self.root,REGISTRY,proto,master)
        item['families'].pop()
        with self.assertRaises(RuntimeError):
            ctrl.plan_state(item,self.profiles)
if __name__=='__main__':unittest.main()
