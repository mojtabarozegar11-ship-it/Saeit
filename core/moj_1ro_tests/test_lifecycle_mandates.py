import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from core.moj_1ro import lifecycle_mandates as lm
from core.moj_1ro import executive_runtime as ex
from core.moj_1ro.operational_law import current
from core.moj_1ro.foundation_runtime import connect

class LifecycleMandateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.c=connect(Path(self.tmp.name)/'runtime.sqlite3')
    def tearDown(self):self.c.close();self.tmp.cleanup()
    def test_all_twenty_milestones_persist_without_claiming_completion(self):
        lm.sync(self.c)
        self.assertEqual(self.c.execute('SELECT count(*) FROM lifecycle_milestones').fetchone()[0],20)
        self.assertEqual(set(r[0] for r in self.c.execute('SELECT state FROM lifecycle_milestones')),{'unverified'})
    def test_repeated_planning_preserves_verified_evidence(self):
        lm.sync(self.c)
        self.c.execute("UPDATE lifecycle_milestones SET state='verified',evidence='owner_record' WHERE domain='games' AND phase='owner_acceptance'")
        self.c.commit();lm.sync(self.c)
        r=self.c.execute("SELECT state,evidence FROM lifecycle_milestones WHERE domain='games' AND phase='owner_acceptance'").fetchone()
        self.assertEqual(tuple(r),('verified','owner_record'))
    def test_repository_boundaries_and_owner_acceptance(self):
        games=lm.roadmap('games',self.c);finance=lm.roadmap('finance_commerce',self.c)
        self.assertEqual({r['repository'] for r in games},{'Bazei'})
        self.assertEqual({r['repository'] for r in finance},{'Saeit'})
        self.assertIn('owner_acceptance',{r['phase'] for r in games})
    def test_existing_executive_objective_updates_without_losing_receipt(self):
        ex.schema(self.c)
        self.c.execute("UPDATE executive_goals SET objective='old',last_result='receipt',last_run=123 WHERE domain='games'")
        self.c.commit();ex.schema(self.c)
        r=self.c.execute("SELECT objective,last_result,last_run FROM executive_goals WHERE domain='games'").fetchone()
        self.assertEqual(r['objective'],ex.DOMAINS['games']['objective'])
        self.assertEqual(r['last_result'],'receipt');self.assertEqual(r['last_run'],123)
    def test_missing_workspace_not_promoted_to_playable_game(self):
        with patch.object(lm,'GAME_ROOT',Path(self.tmp.name)/'missing'),patch.object(lm,'roadmap',return_value=[]):
            r=lm.games_audit()
        self.assertEqual(r['state'],'blocked');self.assertFalse(r['game_build_executed'])
        self.assertEqual(r['target_market'],'USA');self.assertFalse(r['game_two_allowed'])
    def test_optional_nft_rule_does_not_claim_financial_connection(self):
        spec=current()['article_3']['games']['optional_digital_assets']
        self.assertTrue(spec['enabled_as_option'])
        self.assertTrue(spec['requirements'])
    def test_financial_model_inventory_not_end_to_end_operational_proof(self):
        inventory={'ledger_imbalance_groups':0,'ledger_inspection_complete':True,'wallet_records':3}
        with patch.object(lm,'financial_inventory',return_value=inventory),patch.object(lm,'business_snapshot',return_value={}),patch.object(lm,'roadmap',return_value=[]):
            r=lm.finance_audit()
        self.assertEqual(r['state'],'blocked');self.assertFalse(r['production_readiness_verified'])
        self.assertFalse(r['game_finance_connected']);self.assertEqual(r['transactions_executed'],0)
    def test_imbalanced_ledger_is_reported_as_blocker(self):
        with patch.object(lm,'financial_inventory',return_value={'ledger_imbalance_groups':2,'ledger_inspection_complete':True}),patch.object(lm,'business_snapshot',return_value={}),patch.object(lm,'roadmap',return_value=[]):
            self.assertIn('posted_ledger_imbalance',lm.finance_audit()['missing'])
