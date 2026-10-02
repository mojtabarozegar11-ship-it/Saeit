import json, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from core.moj_1ro import executive_runtime as ex
from core.moj_1ro.foundation_runtime import connect
from core.moj_1ro.executable_catalog import handlers,classification

OWNER=SimpleNamespace(pk=1,is_staff=True,is_superuser=False)
class ExecutiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.c=connect(Path(self.tmp.name)/'runtime.sqlite3')
        ex.schema(self.c)
    def tearDown(self):
        self.c.close();self.tmp.cleanup()
    def submit(self,domain='site',operation='audit',payload=None,**kw):
        return ex.submit(domain,operation,payload,owner=OWNER,connection=self.c,**kw)
    def test_five_domain_goals_without_new_robots(self):
        self.assertEqual(set(ex.portfolio(self.c)['domains']),set(ex.DOMAINS))
    def test_repository_boundaries(self):
        p=ex.portfolio(self.c)['domains']
        self.assertEqual(p['games']['repository'],'Bazei')
        self.assertEqual(p['site']['repository'],'Saeit')
    def test_unproved_domains_not_marked_active(self):
        self.assertEqual(ex.portfolio(self.c)['domains']['games']['evidence_status'],'untested')
    def test_submission_is_queued_not_execution(self):
        r=self.submit()
        self.assertFalse(r['executed'])
        self.assertEqual(r['state'],'ready')
    def test_owner_authority_required(self):
        with self.assertRaises(PermissionError):
            ex.submit('site','audit',owner=None,connection=self.c)
    def test_auto_mutation_rejected(self):
        with self.assertRaises(PermissionError):
            ex.submit('site','apply_patch',{'changes':[{'path':'core/x.py','content':'x=1','expected_sha256':'1'}]},automatic=True,connection=self.c)
    def test_duplicate_request_not_reexecuted(self):
        a=self.submit(request_id='same');b=self.submit(request_id='same')
        self.assertEqual(a['task_id'],b['task_id'])
    def test_changed_idempotency_request_rejected(self):
        self.submit(request_id='same')
        with self.assertRaises(ValueError):
            self.submit(domain='business',request_id='same')
    def test_trading_live_order_not_supported(self):
        with self.assertRaises(ValueError):self.submit('trading','place_order')
    def test_costs_not_fabricated(self):
        with self.assertRaises(ValueError):self.submit('economics','unit_economics',{'price':10})
    def test_economic_calculation_real_but_not_realized_profit(self):
        p={'price':10,'variable_cost':3,'fixed_cost':20,'units':10,'currency':'TRX'}
        r=ex.perform('economics','unit_economics',p)
        self.assertEqual(r['calculation']['profit'],'50')
        self.assertIsNone(r['realized_profit'])
    def test_negative_cost_rejected(self):
        with self.assertRaises(ValueError):
            ex.validate('economics','unit_economics',{'price':1,'variable_cost':-1,'fixed_cost':0,'units':2,'currency':'TRX'})
    def test_backtest_has_no_real_trades(self):
        r=ex.backtest({'prices':list(range(1,31)),'window':5,'cost_rate':.001})
        self.assertEqual(r['live_trades'],0)
        self.assertIsNone(r['live_profit'])
        self.assertGreater(r['return_pct'],0)
    def test_backtest_flat_series_not_profitable(self):
        r=ex.backtest({'prices':[10]*30,'window':5,'cost_rate':.001})
        self.assertEqual(r['return_pct'],0)
    def test_backtest_invalid_prices_rejected(self):
        with self.assertRaises(ValueError):
            ex.validate('trading','backtest',{'prices':[float('nan')]*30})
    def test_priority_controls_actual_execution(self):
        low=self.submit(domain='economics',priority=1)
        high=self.submit(domain='site',priority=99)
        with patch.object(ex,'perform',return_value={'state':'observed','repairs_applied':0}),patch.object(ex,'BASE',Path(self.tmp.name)):
            r=ex.run_one(self.c,1e12)
        self.assertEqual(r['task_id'],high['task_id'])
        self.assertNotEqual(r['task_id'],low['task_id'])
    def test_failed_executor_not_success(self):
        r=self.submit()
        with patch.object(ex,'perform',side_effect=RuntimeError('failure')):
            result=ex.run_one(self.c,1e12)
        self.assertEqual(result['state'],'blocked')
        self.assertEqual(self.c.execute('SELECT state FROM executive_tasks WHERE id=?',(r['task_id'],)).fetchone()[0],'blocked')
    def test_receipt_persisted_and_verified(self):
        self.submit()
        with patch.object(ex,'perform',return_value={'state':'observed'}),patch.object(ex,'BASE',Path(self.tmp.name)):
            r=ex.run_one(self.c,1e12)
            self.assertTrue(Path(r['evidence_path']).exists())
            self.assertEqual(len(r['evidence_sha256']),64)
    def test_expired_lease_recovered_without_false_success(self):
        r=self.submit()
        self.c.execute("UPDATE executive_tasks SET state='running',lease_until=1 WHERE id=?",(r['task_id'],));self.c.commit()
        result=ex.run_one(self.c,1000)
        self.assertEqual(result['state'],'idle')
        self.assertEqual(self.c.execute('SELECT state FROM executive_tasks WHERE id=?',(r['task_id'],)).fetchone()[0],'retry')
    def test_registry_templates_not_advertised_as_execution(self):
        self.assertEqual(set(handlers({'game.build':object(),'status':object()})),{'status','executive.status','executive.submit'})
    def test_advisor_is_advice_not_execution(self):
        self.assertEqual(classification('advisor.consult'),'advisory_only')

    def test_owner_reply_does_not_claim_queued_action_was_executed(self):
        from core.moj_1ro.executive_chat import format_result
        reply=format_result('executive.submit',{'state':'ready'})
        self.assertIn('صف اجرا',reply)
        self.assertNotIn('با موفقیت انجام',reply)
    def test_owner_status_lists_blockers_without_promoting_expertise(self):
        from core.moj_1ro.executive_chat import format_result
        reply=format_result('executive.status',{'portfolio':ex.portfolio(self.c)})
        self.assertIn('آزمایش نشده',reply)
        self.assertIn('اثبات نشده',reply)
