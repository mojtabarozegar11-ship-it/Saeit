import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core.moj_1ro import foundation_runtime as rt, executive_runtime as ex
from core.moj_1ro.customer_path import prepare_handoff, snapshot

OFFER = {'id':1,'title':'Automation Audit','type':'ai_automation','price':'49','currency':'TRX'}
SNAP = {'orders':0,'paid_orders':0,'revenue':'0'}
URL = 'https://www.freelancer.com/projects/ai-automation/audit'
READINESS = {'purchasable':False,'missing':['product_quality_approval']}

class CustomerPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.c = rt.connect(Path(self.tmp.name)/'runtime.sqlite3')
    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()
    def test_existing_drafts_advance_once_without_becoming_customers(self):
        self.c.execute("INSERT INTO opportunities VALUES(?,?,'draft_ready',NULL,1000)",
                       (URL,json.dumps({'url':URL,'product_id':1,'excerpt':'audit request'})))
        self.c.commit()
        rt.plan(self.c,OFFER,SNAP,1000)
        rt.plan(self.c,OFFER,SNAP,1000)
        task=rt.claim(self.c,1000)
        self.assertEqual(task['kind'],'handoff')
        with patch.object(rt,'BASE',Path(self.tmp.name)), patch.object(rt,'offer_readiness',return_value=READINESS):
            result=rt.commit(self.c,task,rt.execute(task),1001)
            artifact=json.loads(Path(result['artifact']).read_text())
        self.assertEqual(result['state'],'completed')
        self.assertFalse(artifact['sent'])
        self.assertFalse(artifact['purchasable'])
        self.assertEqual(artifact['contact_route']['url'],URL)
        self.assertIn('authenticated_marketplace_account',artifact['missing'])
        rt.plan(self.c,OFFER,SNAP,1002)
        self.assertEqual(self.c.execute("SELECT count(*) FROM tasks WHERE kind='handoff'").fetchone()[0],1)
        self.assertEqual(snapshot(self.c)['verified_customers'],0)
    def test_customer_route_rejects_embedded_credentials(self):
        with self.assertRaises(ValueError):
            prepare_handoff({'url':'https://user:secret@example.org'},OFFER,READINESS)
    def test_readiness_does_not_treat_active_product_as_quality_approved(self):
        fake=type('Product',(),{'DoesNotExist':type('Missing',(Exception,),{}),
                             'objects':type('Manager',(),{'get':lambda *a,**kw:object()})()})
        gate=type('Pipeline',(),{'can_publish':lambda p:False})
        with patch.object(rt,'Product',fake),patch.dict('sys.modules',{'core.product_pipeline':gate}):
            self.assertEqual(rt.offer_readiness(OFFER),READINESS)
    def test_failed_executive_updates_goal_receipt(self):
        ex.schema(self.c)
        from types import SimpleNamespace
        ex.submit('business','audit',owner=SimpleNamespace(pk=1,is_staff=True),connection=self.c)
        with patch.object(ex,'perform',side_effect=RuntimeError()):
            result=ex.run_one(self.c,1e12)
        goal=self.c.execute("SELECT last_result,last_run FROM executive_goals WHERE domain='business'").fetchone()
        self.assertEqual(json.loads(goal['last_result'])['state'],'blocked')
        self.assertGreater(goal['last_run'],0)
    def test_planner_does_not_accumulate_pending_audits(self):
        now=[1000]
        with patch.object(ex,'connect',side_effect=lambda:rt.connect(Path(self.tmp.name)/'planner.sqlite3')), \
             patch.object(ex,'run_one',return_value={'state':'idle'}), \
             patch.object(ex,'atomic_json'),patch.object(ex.time,'time',side_effect=lambda:now[0]):
            ex.tick(1)
            now[0]=10000
            frame=ex.tick(2)
        self.assertEqual(frame['states']['ready'],len(ex.DOMAINS))
