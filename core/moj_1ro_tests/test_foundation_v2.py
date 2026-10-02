import json, tempfile, time, unittest
from pathlib import Path
from unittest.mock import patch
from core.moj_1ro import foundation_runtime as rt
from core.moj_1ro.foundation_demand import analyse, proposal

OFFER = {'id': 1, 'title': 'Automation Audit', 'type': 'ai_automation',
         'price': '49', 'currency': 'TRX'}
SNAP = {'orders': 0, 'paid_orders': 0, 'revenue': '0'}

class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.c = rt.connect(Path(self.tmp.name) / 'test.sqlite3')
    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()
    def test_plain_listing_is_not_buyer(self):
        r = analyse('<p>Services automation procurement tender</p>',
                    'https://example.org/list', OFFER)
        self.assertIsNone(r['candidate'])
    def test_actual_text_has_intent_and_offer_need(self):
        r = analyse('<p>Request for proposal: workflow automation</p>',
                    'https://example.org/rfp/12', OFFER, True)
        self.assertIsNotNone(r['candidate'])
        self.assertFalse(r['candidate']['verified_buyer'])
    def test_unrelated_tender_is_not_candidate(self):
        r = analyse('<p>Tender for irrigation and fertilizer</p>',
                    'https://example.org/rfp/12', OFFER, True)
        self.assertIsNone(r['candidate'])
    def test_links_extracted_and_unsafe_targets_excluded(self):
        html = '<a href="/rfp/12">RFP workflow automation</a><a href="https://evil.org/">RFP automation</a><a href="/login">RFP automation</a>'
        r = analyse(html, 'https://example.org/list', OFFER)
        self.assertEqual([x['url'] for x in r['links']], ['https://example.org/rfp/12'])
    def test_script_text_not_evidence(self):
        r = analyse('<script>request for proposal automation</script><p>Home</p>',
                    'https://example.org/detail', OFFER, True)
        self.assertIsNone(r['candidate'])
    def test_keyword_substrings_not_buyer_intent(self):
        r = analyse('<p>Seekingness automation</p>', 'https://example.org/detail', OFFER, True)
        self.assertIsNone(r['candidate'])
    def test_draft_cannot_claim_sent_or_customer(self):
        draft = proposal({'url': 'https://example.org/1', 'excerpt': 'RFP workflow'}, OFFER)
        self.assertFalse(draft['sent'])
        self.assertIn('buyer_identity', draft['checks_required'])
    def test_plan_is_idempotent_and_resume_keeps_task(self):
        rt.plan(self.c, OFFER, SNAP, 1000)
        rt.plan(self.c, OFFER, SNAP, 1000)
        self.assertEqual(self.c.execute("SELECT count(*) FROM tasks WHERE kind='fetch'").fetchone()[0], 1)
    def test_claim_exclusive_and_crash_recovery(self):
        rt.plan(self.c, OFFER, SNAP, 1000)
        task = rt.claim(self.c, 1000)
        self.assertEqual(self.c.execute("SELECT state FROM tasks WHERE id=?", (task['id'],)).fetchone()[0], 'running')
        rt.plan(self.c, OFFER, SNAP, 1100)
        recovered = self.c.execute("SELECT state,not_before FROM tasks WHERE id=?", (task['id'],)).fetchone()
        self.assertEqual(recovered[0], 'retry')
        self.assertGreater(recovered[1], 1100)
    def test_timeout_recorded_blocked_and_source_backoff(self):
        rt.plan(self.c, OFFER, SNAP, 1000)
        row = self.c.execute("SELECT * FROM tasks WHERE kind='fetch'").fetchone()
        task = dict(row)
        src = json.loads(task['payload'])['source']
        result = rt.commit(self.c, task, {'state': 'blocked', 'reason': 'executor_timeout', 'source': src}, 1000)
        self.assertEqual(result['state'], 'blocked')
        self.assertGreater(self.c.execute("SELECT next_at FROM sources WHERE url=?", (src['url'],)).fetchone()[0], 1000)
    def test_repetition_has_no_effect(self):
        rt.plan(self.c, OFFER, SNAP, 1000)
        task = dict(self.c.execute("SELECT * FROM tasks WHERE kind='fetch'").fetchone())
        src = json.loads(task['payload'])['source']
        result = rt.commit(self.c, task, {'state': 'completed', 'source': src,
                       'evidence': {'links': [], 'candidate': None}}, 1000)
        self.assertEqual(result['state'], 'no_effect')
    def test_after_blocker_planner_selects_other_source(self):
        rt.plan(self.c, OFFER, SNAP, 1000)
        task = dict(self.c.execute("SELECT * FROM tasks WHERE kind='fetch'").fetchone())
        src = json.loads(task['payload'])['source']
        rt.commit(self.c, task, {'state': 'blocked', 'reason': 'http_error', 'source': src}, 1000)
        rt.plan(self.c, OFFER, SNAP, 1001)
        row = self.c.execute("SELECT payload FROM tasks WHERE kind='fetch' AND state='ready'").fetchone()
        self.assertNotEqual(json.loads(row[0])['source']['url'], src['url'])
    def test_candidate_leads_to_persisted_verified_draft(self):
        rt.plan(self.c, OFFER, SNAP, 1000)
        self.c.execute("INSERT INTO opportunities VALUES(?,?,'candidate',NULL,1000)",
                       ('https://example.org/rfp/1', json.dumps({'url':'https://example.org/rfp/1','excerpt':'Workflow RFP'})))
        self.c.commit()
        rt.plan(self.c, OFFER, SNAP, 1001)
        task = rt.claim(self.c, 1001)
        self.assertEqual(task['kind'], 'draft')
        with patch.object(rt, 'BASE', Path(self.tmp.name)):
            result = rt.commit(self.c, task, rt.execute(task), 1002)
            self.assertTrue(Path(result['artifact']).exists())
        self.assertEqual(self.c.execute('SELECT state FROM opportunities').fetchone()[0], 'draft_ready')
    def test_health_cannot_count_as_business_success(self):
        self.assertFalse(any(rt.outcome(SNAP, SNAP).values()))
    def test_order_without_payment_is_not_revenue(self):
        after = dict(SNAP, orders=1)
        self.assertTrue(rt.outcome(SNAP, after)['order_growth'])
        self.assertFalse(rt.outcome(SNAP, after)['revenue_growth'])
    def test_executor_deadline_is_real(self):
        def slow(sender, url):
            time.sleep(1)
        with patch.object(rt, '_fetch_child', slow):
            r = rt.bounded_fetch('https://example.org/', deadline=0.05)
        self.assertEqual(r['error'], 'executor_timeout')
    def test_unknown_capability_is_blocked(self):
        self.assertEqual(rt.execute({'kind':'arbitrary_shell','payload':'{}'})['state'], 'blocked')
    def test_summary_is_honest_about_attribution(self):
        rt.plan(self.c, OFFER, SNAP, 1000)
        with patch.object(rt, 'offer_readiness', return_value={'purchasable':False,'missing':['product_quality_approval']}):
            row = rt.summary(self.c, 1, SNAP, OFFER, {'state':'completed'})
        self.assertEqual(row['robot_attributed_revenue'], '0')
        self.assertIn('general_code_repair', row['missing_capabilities'])

    def test_currency_totals_are_not_added_together(self):
        before = dict(SNAP, revenue_by_currency={'TRX':'49','IRR':'100'})
        after = dict(SNAP, revenue_by_currency={'TRX':'49','IRR':'100'})
        self.assertFalse(rt.outcome(before, after)['revenue_growth'])
        after['revenue_by_currency']['TRX'] = '98'
        self.assertTrue(rt.outcome(before, after)['revenue_growth'])

    def test_specific_marketplace_projects_not_navigation(self):
        html = '<a href="/jobs/automation/">Automation jobs</a><a href="/projects/python/workflow-bot">Workflow automation bot</a><a href="/projects/python/workflow-bot">Bid now</a>'
        row = analyse(html, 'https://www.freelancer.com/jobs/automation/', OFFER)
        self.assertEqual(len(row['links']), 1)
        self.assertEqual(row['links'][0]['title'], 'Workflow automation bot')
    def test_actual_project_is_candidate_not_verified_customer(self):
        html = '<p>Project Details. Budget 100. Submit your bid for workflow automation.</p>'
        row = analyse(html, 'https://www.freelancer.com/projects/python/workflow-bot', OFFER, True)
        self.assertIsNotNone(row['candidate'])
        self.assertFalse(row['candidate']['verified_buyer'])

    def test_live_listing_request_can_produce_unverified_evidence(self):
        html = '<a href="/projects/python/automation-audit">Workflow Automation Audit</a><p>6 days left. We need workflow automation. 12 bids.</p>'
        row = analyse(html, 'https://www.freelancer.com/jobs/automation/', OFFER)
        self.assertEqual(len(row['candidates']), 1)
        self.assertFalse(row['candidates'][0]['verified_buyer'])
    def test_expired_listing_is_not_candidate(self):
        html = '<a href="/projects/python/automation-audit">Workflow Automation Audit</a><p>Closed. We need workflow automation.</p>'
        row = analyse(html, 'https://www.freelancer.com/jobs/automation/', OFFER)
        self.assertEqual(row['candidates'], [])

    def test_other_job_description_cannot_qualify_unrelated_title(self):
        html = '<a href="/projects/animation/quality">AI Animation Quality Evaluation</a><p>6 days left. Next listing: workflow automation.</p>'
        row = analyse(html, 'https://www.freelancer.com/jobs/automation/', OFFER)
        self.assertEqual(row['candidates'], [])
