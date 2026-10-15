import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from core.moj_1ro import income_research as ir
from core.moj_1ro import executive_runtime as ex
from core.moj_1ro.foundation_runtime import connect
from core.moj_1ro.operational_law import current,automatic_allowed

SNAPSHOT={'orders':0,'paid_orders':0,'revenue_by_currency':{},'revenue':'0'}
class IncomeResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/'runtime.sqlite3'
    def tearDown(self):self.tmp.cleanup()
    def run_research(self,fetched):
        with patch.object(ir,'connect',side_effect=lambda:connect(self.db)),patch.object(ir,'bounded_fetch',return_value=fetched),patch.object(ir,'business_snapshot',return_value=SNAPSHOT):
            return ir.research()
    def page(self):
        return {'ok':True,'data':{'http_status':200,'content_type':'text/html',
            'body':'<a href="/projects/design/design-animation">Design 3d animation</a> 6 days left Budget $100 5 bids',
            'final_url':'https://www.freelancer.com/jobs/graphic-design/'}}
    def test_mandate_covers_all_five_topics(self):
        self.assertEqual(set(current()['continuous_income_research']['topics']),{x[0] for x in ir.SEEDS})
    def test_research_can_be_queued_without_faking_execution(self):
        c=connect(self.db)
        r=ex.submit('income_research','research',automatic=True,connection=c)
        self.assertEqual(r['state'],'ready');self.assertFalse(r['executed']);c.close()
    def test_automatic_publication_not_authorized(self):
        self.assertFalse(automatic_allowed('income_research','publish',{}))
        self.assertTrue(current()['boundaries']['blog_news_paused'])
    def test_only_empty_payload_allowed_for_automatic_research(self):
        self.assertFalse(automatic_allowed('income_research','research',{'url':'https://unapproved.example'}))
    def test_public_evidence_creates_plan_not_product_or_customer(self):
        result=self.run_research(self.page())
        self.assertEqual(result['new_briefs'],1)
        self.assertFalse(result['verified_buyer'])
        self.assertEqual(result['products_produced'],0)
        c=connect(self.db)
        plan=json.loads(c.execute('SELECT brief FROM income_research_briefs').fetchone()[0]);c.close()
        self.assertFalse(plan['produced']);self.assertFalse(plan['sent'])
        self.assertIsNone(plan['price']);self.assertTrue(plan['quality_checks'])
    def test_duplicate_public_request_not_new_brief(self):
        self.run_research(self.page())
        c=connect(self.db);c.execute('UPDATE income_research_sources SET visits=999')
        c.execute("UPDATE income_research_sources SET visits=0,next_at=0 WHERE topic='digital_assets'");c.commit();c.close()
        self.assertEqual(self.run_research(self.page())['new_briefs'],0)
    def test_failure_has_backoff_and_next_topic_rotates(self):
        first=self.run_research({'ok':False,'error':'executor_timeout'})
        second=self.run_research({'ok':False,'error':'executor_timeout'})
        self.assertEqual(first['state'],'blocked')
        self.assertNotEqual(first['topic'],second['topic'])
        c=connect(self.db);self.assertGreater(c.execute('SELECT next_at FROM income_research_sources WHERE topic=?',(first['topic'],)).fetchone()[0],0);c.close()
    def test_empty_page_not_research_success(self):
        p=self.page();p['data']['body']=''
        self.assertEqual(self.run_research(p)['state'],'blocked')
    def test_receipt_growth_does_not_invent_attribution_or_profit(self):
        before={**SNAPSHOT,'paid_orders':1,'revenue_by_currency':{'TRX':'10'}}
        after={**SNAPSHOT,'paid_orders':2,'revenue_by_currency':{'TRX':'15','USD':'3'}}
        delta=ir.receipt_delta(before,after)
        self.assertEqual(delta['revenue_change_by_currency'],{'TRX':'5','USD':'3'})
        self.assertEqual(delta['robot_attribution'],'not_established')
        self.assertIsNone(delta['verified_profit'])
